import gevent.monkey; gevent.monkey.patch_all()
import bottle
from bottle import run, request, response, post, get, install
import os, sys
import logging
from collections import OrderedDict
import json

log = logging.getLogger()
logging.basicConfig(format='[%(levelname)-8s] %(message)s')
log.setLevel(logging.DEBUG)

class PebbleJSONEncoder(json.JSONEncoder):
     def default(self, obj):
         if isinstance(obj, PebbleValue):
             return obj.asJson()
         # Let the base class default method raise the TypeError
         return json.JSONEncoder.default(self, obj)

json_dumps = json.dumps
class PebbleJSONPlugin(object):
    name = 'pebblejson'
    api  = 2

    def __init__(self, json_dumps=json_dumps):
        self.json_dumps = json_dumps

    def apply(self, callback, route):
        dumps = self.json_dumps
        if not dumps: return callback
        def wrapper(*a, **ka):
            rv = callback(*a, **ka)
            if isinstance(rv, dict):
                pebbleId = request.headers.get('X-Pebble-ID', None)
                accept = request.headers.get('Accept', 'application/vnd.httpebble.named+json')
                r = OrderedDict()
                if pebbleId or accept == 'application/vnd.httpebble.raw+json':
                    i = 1
                    for k in rv:
                        r[str(i)] = rv[k]
                        i+= 1
                elif accept == 'application/json':
                    r = rv
                else:
                    i = 1
                    for k in rv:
                        r[i] = OrderedDict()
                        r[i]['name'] = k
                        r[i]['value'] = rv[k]
                        i += 1
                    
                #Attempt to serialize, raises exception on failure
                json_response = dumps(r, cls=PebbleJSONEncoder)
                #Set content type only if serialization succesful
                response.content_type = 'application/json'
                return json_response
            return rv
        return wrapper

class PebbleValue(object):
    pass

class PebbleInteger(PebbleValue):
    WIDTHS = {
        1:'b',
        2:'s',
        4:'i'
    }

    def asJson(self):
        format = PebbleInteger.WIDTHS[self._width]
        if self._unsigned:
            format = format.upper()
        
        return [format, self._value]

    def __init__(self, value, width, unsigned=True):
        self._value = value
        self._width = width
        self._unsigned = unsigned

def pebbleize(function):
    def inner():
        pebbleId = request.headers.get('X-Pebble-ID')
        data = request.json
        argc = function.func_code.co_argcount-1 #ID is always the first parameter
        name = function.func_code.co_name
        if data is None:
            log.error("Invalid request data - couldn't get JSON")
            return None #TODO: Error codes.
        if len(data) != argc:
            log.error("Argument count mismatch calling %s - expected %d got %d" % (name, argc, len(data)))
            return None #TODO: Come up with a reasonable error code return mechanism.
        args = []
        for key in xrange(argc):
            k = str(key+1)
            args.append(data[k])
        
        return function(pebbleId, *args)

    return inner

@post('/')
@pebbleize
def post_random(id, length):
    #Chosen by fair die roll. Guaranteed to be random.
    rng = "".join("4" for x in xrange(length))
    log.debug("Random number: %s" % repr(rng))
    return OrderedDict([("random", rng)])

if __name__=="__main__":
    bottle.debug(True)
    install(PebbleJSONPlugin())
    run(server='gevent', host='0.0.0.0', port=os.environ.get('PORT', 5000), autojson=True)
