import json


class ZervRequest(object):
    def __init__(self, event):
        self._parse_event(event)

    def _parse_event(self, event):
        self.event = event
        self.headers = event.get('headers', {})
        self.query_params = event.get('queryStringParameters', {})
        self.body = event.get('body')

        try:
            self.json_body = json.loads(self.body)
        except BaseException:
            self.json_body = {}


class ZervResponse(object):
    def __init__(self, plain_body, headers=None, json_format=True, status_code=200):
        self.is_json = json_format
        self.status_code = status_code
        self.headers = headers or {}
        self.body = plain_body

        self._prepare()

    def _prepare(self):
        if self.is_json:
            self.headers['Content-Type'] = 'application/json'
            self.body = json.dumps(self.body)

    def as_aws(self):
        return dict(
            isBase64Encoded=True,
            statusCode=self.status_code,
            headers=self.headers,
            body=self.body
        )


class ZervBadRequest(BaseException):
    def __init__(self, payload):
        self.headers = {'Content-Type': 'plain/text'}
        self.body = payload
        if isinstance(payload, dict):
            self.headers = {'Content-Type': 'application/json'}
            self.body = json.dumps(payload)

    def as_response(self):
        return dict(
            isBase64Encoded=True,
            statusCode=400,
            headers=self.headers,
            body=self.body
        )


class ZervInternalServerError(Exception):
    def __init__(self, error, debug=False):
        self.error = error
        self.headers = {'Content-Type': 'application/json'}
        self.debug = debug

    def as_response(self):
        body = dict(message='Internal server error')
        if self.debug:
            body['error'] = str(self.error)

        return dict(
            isBase64Encoded=True,
            statusCode=500,
            headers=self.headers,
            body=json.dumps(body)
        )
