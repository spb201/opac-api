import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import re
from xmltodict import XmlListConfig
from functools import reduce


class OPACConnectionException(Exception):
    pass


class OPACWrapper(object):
    DEFAULT_LENGTH = 10

    username = 'GUEST'
    password = 'GUESTE'
    type_access = 'PayAccess'

    OPAC_INIT_URL = 'http://opac.omsklib.ru/cgiopac/opacg/opac.exe'
    OPAC_DIRECT_URL = 'http://opac.omsklib.ru/cgiopac/opacg/direct.exe'

    session_id = '-1'

    def __init__(self):
        # trying to get session_id from opac
        params = urllib.parse.urlencode({'arg0': self.username, 'arg1': self.password, 'TypeAccess': self.type_access})
        url = self.OPAC_INIT_URL + '?{0}'.format((params,))
        with urllib.request.urlopen(url) as f:
            response = False

            # trying to connect three times since opac sometimes fails to send a response
            for i in range(1, 3):
                try:
                    response = f.read().decode('utf-8').split('\r\n')
                    break
                except UnicodeDecodeError:
                    pass
            if not response:
                raise OPACConnectionException

            for line in response:
                if not line.find('numsean') == -1:
                    self.session_id = re.findall(r'"([^"]*)"', line)[0]

    def get_book_list(self, query_map, length=DEFAULT_LENGTH, offset=0):
        """
        :param query_map: content of the query to be searched
        :param length: maximum length of returned books list
        :param offset: books offset length
        :return: length, books: tuple, where first element is total amount of books, which can be found with this query
                                             second element is list of books
        """
        def escape_query(query):
            return query.replace("'", " ")

        def generate_query(m):
            m = filter(lambda x: x[1] is not None, m.items())
            unescaped_query = ' AND '.join(reduce(lambda acc, cur: acc.append('({0} {1})'.format(*cur)) or acc, m, []))
            return escape_query(unescaped_query)

        data = urllib.parse.urlencode({'_errorXsl': '/opacg/html/common/xsl/error.xsl',
                                       '_wait:6M': '_xsl:/opacg/html/search/xsl/search_results.xsl',
                                       '_version': '2.5.0', '_service': 'STORAGE:opacfindd:FindView',
                                       'outformList[0]/outform': 'SHOTFORM', 'outformList[1]/outform': 'LINEORD',
                                       'length': length, 'start': offset, 'level[0]': 'Full', 'level[1]': 'Retro',
                                       'query/body': generate_query(query_map),
                                       'query/open': "{NC:<span class='red_text'>}", 'query/close': '{NC:</span>}',
                                       'userId': self.username, 'session': self.session_id, 'iddb': '2'})
        url = self.OPAC_DIRECT_URL
        with urllib.request.urlopen(url, data=data.encode('UTF-8')) as f:
            response = f.read().decode('utf-8')
            tree = ET.ElementTree(ET.fromstring(response))
            root = tree.getroot()
            size = reduce(lambda a, b: a + (b[1] if b[0] == 'size' else ''), root.items(), '')

            if size == '':
                return 0, []

            if int(size) == 1 or int(length) == 1:
                books = (XmlListConfig(root)[0]['entry']['SHOTFORM']['content']['entry'],)
            else:
                books = map(lambda i: i['SHOTFORM']['content']['entry'],
                            XmlListConfig(root)[0]) if not size == '0' else []

            return size, list(books)
