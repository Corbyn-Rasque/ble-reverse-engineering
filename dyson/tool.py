import getpass, ssl, json, certifi
import urllib.parse, urllib.request
from enum import StrEnum, Enum
from argparse import ArgumentParser, Namespace

PROGRAM = 'Dyson Account GUID Printer'
AUTHOR  = 'Corbyn Rasque'
VERSION = 1.0

PRINT_WIDTH = 14

class Parser:
    ARGUMENTS = (
        {
            'flags':    ['email'],
            'kwargs':   {
                'type':     str,
                'default':  None,
                'nargs':    '?',
                "metavar":  'EMAIL',
                'help':     'Dyson account email'
            }
        },
        {
            'flags':        ['password'],
            'kwargs': {
                'type':     str,
                'default':  None,
                'nargs':    '?',
                'metavar':  'PASSWORD',
                'help':     'Dyson account password'
            }
        },
        {
            'flags':        ['country'],
            'kwargs': {
                'type':     str,
                'default':  None,
                'nargs':    '?',
                'metavar':  'COUNTRY',
                'help':     'Dyson account country code (ISO 3166-1 alpha-2)'
            }
        },
        {
            'flags':        ['language'],
            'kwargs': {
                'type':     str,
                'default':  'en-US',
                'nargs':    '?',
                'metavar':  'LANGUAGE',
                'help':     'Dyson account language code (e.g. "en-US")'
            }
        },
        {
            'flags':        ['-e', '--email'],
            'kwargs': {
                'action':   'store_true',
                'dest':     'suppress',
                'help':     'Dyson account email'
            }
        },
        {
            'flags':        ['-p', '--password'],
            'kwargs': {
                'action':   'store_true',
                'dest':     'suppress',
                'help':     'Dyson account password'
            }
        },
        {
            'flags':        ['-c', '--country'],
            'kwargs': {
                'action':   'store_true',
                'dest':     'suppress',
                'help':     'Dyson account country code (ISO 3166-1 alpha-2)'
            }
        },
        {
            'flags':        ['-l', '--language'],
            'kwargs': {
                'action':   'store_true',
                'dest':     'suppress',
                'help':     'Dyson account language code (e.g. "en-US")'
            }
        },
        {
            'flags':        ['-v', '--version'],
            'kwargs': {
                'action':   'version',
                'version':  '{} {}'.format(PROGRAM, VERSION)
            }
        }
    )

    parser:     ArgumentParser
    arguments:  Namespace

    def __init__(self):
        self.parser = ArgumentParser(description = PROGRAM,
                                     epilog      = 'Written by {}'.format(AUTHOR))
        
        for arg in self.ARGUMENTS:
            self.parser.add_argument(*arg['flags'], **arg['kwargs'])

        self.arguments = self.parser.parse_args()

class API (StrEnum):
    URL         =       "https://appapi.cp.dyson.com"
    PROVISION   = URL + "/v1/provisioningservice/application/Android/version"
    STATUS      = URL + "/v3/userregistration/email/userstatus"
    AUTH        = URL + "/v3/userregistration/email/auth"
    VERIFY      = URL + "/v3/userregistration/email/verify"
    LTK         = URL + "/v1/lec/{serial}/ltk"

class Request:
    class Method (StrEnum):
        GET     = "GET"
        POST    = "POST"

    HEADER = { 
        "User-Agent":   "android client",
        "Accept":       "application/json" 
    }

    @classmethod
    def request(cls, method: str, 
                     url: str, 
                     params: dict | None = None, 
                     header: dict | None = None, 
                     body: dict | None = None):
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = None
        header = header or dict(cls.HEADER)

        if body is not None:
            data = json.dumps(body).encode("utf-8")
            header["Content-Type"] = "application/json"

        request = urllib.request.Request(
            url     = url, 
            data    = data, 
            headers = header,
            method  = method
        )
        context = ssl.create_default_context(cafile=certifi.where())

        with urllib.request.urlopen(request, context = context) as response:
            return response.read()
        
    @classmethod
    def get(cls, url: str, 
                 params: dict | None = None, 
                 header: dict | None = None, 
                 body: dict | None = None) -> dict:
        response = cls.request(Request.Method.GET, url, params, header, body)
        return json.loads(response) if response else {}

    @classmethod
    def post(cls, url: str, 
                  params: dict | None = None, 
                  header: dict | None = None, 
                  body: dict | None = None) -> dict:
        response = cls.request(Request.Method.POST, url, params, header, body)
        return json.loads(response) if response else {}

class Account:
    class Status (StrEnum):
        ACTIVE = "ACTIVE"
        ...

    email:      str
    password:   str
    country:    str
    token:      str | None = None
    guid:       str | None = None
    ltk:        str | None = None

    def __init__(self, email:    str | None = None, 
                       password: str | None = None, 
                       country:  str | None = None,
                       language: str | None = None):
        if not email or not password or not country or not language:
            self.parse()
        else:
            self.email      = email
            self.password   = password
            self.country    = country
            self.language   = language

        # Provision API Access for IP Address
        Request.get(API.PROVISION)

        # Check status of account
        match (status := Request.post(url     = API.STATUS, 
                                      params  = {"country": self.country}, 
                                      body    = {"email": self.email}
                                      )['accountStatus']):
            case Account.Status.ACTIVE: pass
            case _:                     ValueError("Account status {status}")
            
        # Request OTP Code by Email
        challenge = Request.post(url    = API.AUTH,
                                 params = {"country": self.country, "culture": self.language},
                                 body   = {"email": self.email}
                                 )["challengeId"]
        
        # Input OTP Code
        code = input(f"{"OTP Code:":{PRINT_WIDTH}}")

        # Get GUID
        info = Request.post(url     = API.VERIFY,
                            body    = {
                                "email":        self.email,
                                "password":     self.password,
                                "challengeId":  challenge,
                                "otpCode":      code,
                            }
                            )

        self.token  = info.get('token')
        self.guid   = info.get('account')

    def parse(self):
        arguments = Parser().arguments

        self.email      = arguments.email or \
                          input(f'{'Email:':{PRINT_WIDTH}}')
        self.password   = arguments.password or \
                          getpass.getpass(f'{'Password:':{PRINT_WIDTH}}')
        self.country    = arguments.country or \
                          input(f'{'Country Code:':{PRINT_WIDTH}}')
        self.language   = arguments.language or \
                          input(f'{'Language:':{PRINT_WIDTH}}')

    def key(self, apiAuthCode: str, serial: str) -> str | None:
        response = Request.get(
            url     = API.LTK.format(serial = serial),
            header = {
                "Authorization":       f"Bearer {self.token}",
                "X-Dyson-ApiAuthCode": apiAuthCode,
            },
        )
        self.ltk = response["ltk"]
        return self.ltk

    def __str__(self) -> str:
        return f"{"GUID:":{PRINT_WIDTH}}{self.guid}\n{"LTK:":{PRINT_WIDTH}}{self.ltk}"

if __name__ == "__main__":
    print(Account())