from guillotina import testing
from guillotina.component import get_utility
from guillotina.interfaces import ICatalogUtility
from guillotina.tests.utils import ContainerRequesterAsyncContextManager
from guillotina_elasticsearch.interfaces import IConnectionFactoryUtility
from guillotina_elasticsearch.tests.utils import cleanup_es

import os
import pytest


def base_settings_configurator(settings):
    if 'applications' not in settings:
        settings['applications'] = []

    if 'guillotina_elasticsearch' not in settings['applications']:
        settings['applications'].append('guillotina_elasticsearch')

    if 'guillotina_elasticsearch.tests.package' not in settings['applications']:  # noqa
        settings['applications'].append(
            'guillotina_elasticsearch.tests.package')

    settings['elasticsearch'] = {
        "index_name_prefix": "guillotina-",
        "connection_settings": {
            "hosts": ['{}:{}'.format(
                getattr(elasticsearch, 'host', 'localhost'),
                getattr(elasticsearch, 'port', '9200'),
            )],
            "sniffer_timeout": None
        }
    }

    if os.environ.get('ES_VERSION', '6') == 'OPEN_DISTRO':
        settings['elasticsearch']["connection_settings"].update({
            "use_ssl": True,
            "http_auth": "admin:admin"
        })

    settings["load_utilities"]["catalog"] = {
        "provides": "guillotina_elasticsearch.interfaces.IElasticSearchUtility",  # noqa
        "factory": "guillotina_elasticsearch.utility.ElasticSearchUtility",
        "settings": {}
    }


testing.configure_with(base_settings_configurator)


@pytest.fixture(scope='session')
def elasticsearch(es):
    host, port = es

    setattr(elasticsearch, 'host', host)
    setattr(elasticsearch, 'port', port)

    yield es


class ESRequester(ContainerRequesterAsyncContextManager):
    def __init__(self, guillotina, loop):
        super().__init__(guillotina)
        self.loop = loop

    async def __aenter__(self):
        # aioelasticsearch caches loop, we need to continue to reset it
        search = get_utility(ICatalogUtility)

        util = get_utility(IConnectionFactoryUtility)
        await util.close(search.loop)
        search.loop = self.loop

        from guillotina import app_settings
        if os.environ.get('TESTING', '') == 'jenkins':
            if 'elasticsearch' in app_settings:
                app_settings['elasticsearch']['connection_settings']['hosts'] = [  # noqa
                    '{}:{}'.format(
                        getattr(elasticsearch, 'host', 'localhost'),
                        getattr(elasticsearch, 'port', '9200'),
                    )]
        return await super().__aenter__()


@pytest.fixture(scope='function')
async def es_requester(elasticsearch, guillotina, loop):
    # clean up all existing indexes
    es_host = '{}:{}'.format(
        elasticsearch[0], elasticsearch[1])
    await cleanup_es(es_host)
    return ESRequester(guillotina, loop)
