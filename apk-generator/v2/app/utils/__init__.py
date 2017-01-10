import shutil
import zipfile
import os
from tempfile import mkstemp
import errno


def replace(file_path, pattern, subst):
    """
    Replace a string in a file
    :param file_path: The path to the file
    :param pattern: The patter to search for
    :param subst: The substitute string
    :return:
    """
    # Create temp file
    fh, abs_path = mkstemp()
    with open(abs_path, 'w') as new_file:
        with open(file_path) as old_file:
            for line in old_file:
                new_file.write(line.replace(pattern, subst))
    os.close(fh)
    # Remove original file
    os.remove(file_path)
    # Move new file
    shutil.move(abs_path, file_path)


def unzip(source_file, target_dir):
    """
    Unzip a zip archive into a target directory
    :param source_file: the path to the archive
    :param target_dir: the path to the destination directory
    :return:
    """
    with open(source_file, "rb") as zip_src:
        zip_file = zipfile.ZipFile(zip_src)
        for member in zip_file.infolist():
            target_path = os.path.join(target_dir, member.filename)
            if target_path.endswith('/'):  # folder entry, create
                try:
                    os.makedirs(target_path)
                except (OSError, IOError) as err:
                    # Windows may complain if the folders already exist
                    if err.errno != errno.EEXIST:
                        raise
                continue
            with open(target_path, 'wb') as outfile, zip_file.open(member) as infile:
                shutil.copyfileobj(infile, outfile)
