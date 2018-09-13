import os
from copy import deepcopy

class NOT_PROVIDED:
    pass

def merge_dicts(first_dict, second_dict):
    """This will combine two dict
    """
    first_dict = deepcopy(first_dict)
    second_dict = deepcopy(second_dict)
    merge_dict = {}
    for key, default_value in first_dict.items():
        # Remove keys being used
        settings_value = second_dict.pop(key, NOT_PROVIDED)
        if settings_value is NOT_PROVIDED:
            merge_dict[key] = default_value
        else:
            if isinstance(default_value, dict) and isinstance(settings_value, dict):
                new_value = merge_dicts(default_value, settings_value)
            else:
                new_value = settings_value
            merge_dict[key] = new_value
    # Remaining keys
    return dict(**merge_dict, **second_dict)


def zip_write_dir(zip_fileobj, dir_path, files_prefix=''):
    for dirpath, dirnames, dirfiles in os.walk(dir_path):
        for dirname in dirnames:
            if files_prefix:
                dir_prefix = '%s/%s' % (files_prefix, dirname)
            else:
                dir_prefix = dirname
            dir_path = os.path.join(dirpath, dirname)
            zip_write_dir(zip_fileobj, dir_path, files_prefix=dir_prefix)

        for filename in dirfiles:
            file_path = os.path.join(dirpath, filename)
            zip_fileobj.write(file_path, '%s/%s' % (files_prefix, filename))
