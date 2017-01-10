import os

import logging

import sys

from celery import Celery
from celery.signals import after_task_publish
from flask import Flask
from flask import json
from flask import render_template
from flask.ext.htmlmin import HTMLMIN

from app.utils.flask_helpers import SilentUndefined, request_wants_json

app = Flask(__name__)


class ReverseProxied(object):
    """
    ReverseProxied flask wsgi app wrapper from http://stackoverflow.com/a/37842465/1562480 by aldel
    """
    def __init__(self, _app):
        self.app = _app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        if os.getenv('FORCE_SSL', 'no') == 'yes':
            environ['wsgi.url_scheme'] = 'https'
        return self.app(environ, start_response)


app.wsgi_app = ReverseProxied(app.wsgi_app)


def create_app():
    app.config.from_object(os.environ.get('APP_CONFIG', 'config.ProductionConfig'))
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.ERROR)
    app.jinja_env.add_extension('jinja2.ext.do')
    app.jinja_env.add_extension('jinja2.ext.loopcontrols')
    app.jinja_env.undefined = SilentUndefined

    # Make sure the working directory exists. If not create it.
    if not os.path.exists(app.config['WORKING_DIR']):
        os.makedirs(app.config['WORKING_DIR'])

    # Make sure the directory is writable
    if not os.access(app.config['WORKING_DIR'], os.W_OK):
        print("The working directory " + app.config['WORKING_DIR'] + " is not writable. Cannot start worker.")
        exit()

    # setup celery
    app.config['CELERY_BROKER_URL'] = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    app.config['CELERY_RESULT_BACKEND'] = app.config['CELERY_BROKER_URL']
    HTMLMIN(app)
    return app


current_app = create_app()


@app.errorhandler(404)
def page_not_found(e):
    if request_wants_json():
        error = {
            'status': 'error',
            'code': 404,
            'message': 'Not Found'
        }
        return json.dumps(error), getattr(error, 'code', 404)
    return render_template('errors/404.html'), 404


def make_celery(_app):
    _celery = Celery(_app.import_name, broker=_app.config['CELERY_BROKER_URL'])
    _celery.conf.update(_app.config)
    task_base = _celery.Task

    class ContextTask(task_base):
        abstract = True

        def __call__(self, *args, **kwargs):
            with _app.app_context():
                return task_base.__call__(self, *args, **kwargs)

    _celery.Task = ContextTask
    return _celery

# register celery tasks. removing them will cause the tasks to not function. so don't remove them
# it is important to register them after celery is defined to resolve circular imports
import tasks


# http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists
@after_task_publish.connect
def update_sent_state(sender=None, body=None, **kwargs):
    # the task may not exist if sent using `send_task` which
    # sends tasks by name, so fall back to the default result backend
    # if that is the case.
    task = celery.tasks.get(sender)
    backend = task.backend if task else celery.backend
    backend.store_result(body['id'], None, 'WAITING')


celery = make_celery(current_app)
