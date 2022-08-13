from . import core as bknd_core
from ..static import cfg as ewcfg

"""
	EwServer is a representation of a server, if the name of the server or
	other meta data is needed in a scope where it's not normally available.
"""


class EwServer:
    id_server = -1

    name = ""
    icon = ""

    def __init__(
            self,
            id_server = None
    ):
        if id_server != None:
            self.id_server = id_server

            # Retrieve object
            data = bknd_core.execute_sql_query("SELECT {}, {} FROM servers WHERE id_server = %s".format(
                ewcfg.col_name,
                ewcfg.col_icon
            ), (self.id_server,))

            if data != ():
                # Record found: apply the data to this object.
                self.name = data[0]
            else:
                # Create a new database entry if the object is missing.
                bknd_core.execute_sql_query("REPLACE INTO servers({}) VALUES(%s)".format(
                    ewcfg.col_id_server
                ), (
                    self.id_server,
                ))

    """ Save server data object to the database. """

    def persist(self):
        if self.icon == None:
            self.icon = ""

        # Save the object.
        bknd_core.execute_sql_query("REPLACE INTO servers({}, {}, {}) VALUES(%s, %s, %s)".format(
            ewcfg.col_id_server,
            ewcfg.col_name,
            ewcfg.col_icon
        ), (
            self.id_server,
            self.name,
            self.icon
        ))


""" update the server record with the current data. """


def server_update(server = None):
    dbserver = EwServer(
        id_server=server.id
    )

    # Update values with Member data.
    dbserver.name = server.name
    dbserver.icon = server.icon_url

    dbserver.persist()
