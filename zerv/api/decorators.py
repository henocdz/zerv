from .http import ZervRequest, ZervBadRequest, ZervInternalServerError, ZervResponse

def route(fixed_token=None, debug=False):
    def _api_route(route_func):
        def _authorized(headers):
            http_authorization = headers.get('Authorization')
            return not fixed_token or (fixed_token and http_authorization == fixed_token)

        def _wrapped_route(event, context, *args, **kwargs):
            zerv_request = ZervRequest(event)
            if _authorized(zerv_request.headers):
                try:
                    zerv_response = route_func(zerv_request)
                except ZervBadRequest as b:
                    return b.as_response()
                except BaseException as e:
                    import traceback
                    str_traceback = str(traceback.format_exc())
                    response = ZervInternalServerError(str_traceback, debug=debug)
                    return response.as_response()
            else:
                zerv_response = ZervResponse(dict(message='Invalid token'), json_format=True, status_code=401)
            return zerv_response.as_aws()
        return _wrapped_route
    return _api_route
