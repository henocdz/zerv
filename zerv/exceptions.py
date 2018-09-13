class ZervSettingsException(Exception):
    def __init__(self, file_name, *args, **kwargs):
        super(Exception, self).__init__(*args, **kwargs)
        self.file_name = file_name

    def __str__(self):
        return "Invalid settings configuration at: %s" % self.file_name


class ZervInvalidSettingsException(Exception):
    pass


class ZervDuplicatedFunction(Exception):
    def __init__(self, name, *args, **kwargs):
        super(Exception, self).__init__(*args, **kwargs)
        self.name = name

    def __str__(self):
        return "Duplicate declaration found for function: %s" % self.name


class ZervUnknownFunction(Exception):
    def __init__(self, name, *args, **kwargs):
        super(Exception, self).__init__(*args, **kwargs)
        self.name = name

    def __str__(self):
        return "Unknown function with name: %s" % self.name
