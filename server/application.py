"""
Authenticated Web application framework.
"""

from past.builtins import basestring
from builtins import str, object
import logging
import cherrypy
from requests.utils import quote
from .authentication import LoginException, Authentication

class Authenticated_Application(object):
    # pylint: disable=no-self-use
    """
    A Web application that requires authentication.
    """

    def __init__(self, args, config):
        auth_type = Authentication.get_type(args.auth)
        self.authentication = auth_type(args, config)

    @cherrypy.expose
    def index(self, page='list', params=''):
        """
        Login form.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    @cherrypy.expose
    def logout(self):
        """
        Log out the user.
        """

        cherrypy.session.pop('authenticated', None)
        cherrypy.lib.sessions.expire()

        raise cherrypy.HTTPRedirect('index')

    def validate_page(self, page):
        """
        Validate a page identifier.
        """

        try:
            getattr(self, page).exposed
        except AttributeError:
            # Invalid method or not exposed
            raise cherrypy.HTTPError(400, 'Page must be valid')

    def validate_login(self, username=None, password=None, page=None,
                       params=None):
        """
        Validate a login request.
        """

        if page is None:
            page = cherrypy.request.path_info.strip('/')

        if params is None:
            params = quote(cherrypy.request.query_string)

        # Redirect on login failure
        redirect = 'index?page={}'.format(page)
        if params != '' and page != '':
            redirect += '&params={}'.format(params)

        if username is not None or password is not None:
            if cherrypy.request.method == 'POST':
                try:
                    result = self.authentication.validate(username, password)
                    logging.info('Authenticated as %s', username)
                    if isinstance(result, basestring):
                        cherrypy.session['authenticated'] = result
                    else:
                        cherrypy.session['authenticated'] = username
                except LoginException as error:
                    logging.info(str(error))
                    raise cherrypy.HTTPRedirect(redirect)
            else:
                raise cherrypy.HTTPError(400, 'POST only allowed for username and password')

        if 'authenticated' not in cherrypy.session:
            logging.info('No credentials or session found')
            raise cherrypy.HTTPRedirect(redirect)

    @cherrypy.expose
    def login(self, username=None, password=None, page='list', params=''):
        """
        Log in the user.
        """

        self.validate_login(username=username, password=password, page=page,
                            params=params)

        # Validate the target page only after logging in
        self.validate_page(page)

        if params != '':
            page += '?' + params
        raise cherrypy.HTTPRedirect(page)

    @cherrypy.expose
    def default(self, *args, **kwargs):
        # pylint: disable=unused-argument
        """
        Default handler for nonexistent pages. These are redirected to the
        index page when not logged in.
        """

        if 'authenticated' not in cherrypy.session:
            raise cherrypy.HTTPRedirect('index')

        raise cherrypy.NotFound()
