"""Register PyMySQL as the MySQL driver when mysqlclient isn't available.

mysqlclient is a C extension and needs libmysqlclient headers plus a compiler,
which serverless build images (Vercel, Lambda) generally don't have. PyMySQL is
pure Python and speaks the same DB-API, so Django's mysql backend accepts it.

Prefers mysqlclient when it *is* installed — it's faster.
"""

try:  # pragma: no cover - import-time driver selection
    import MySQLdb  # noqa: F401
except ImportError:  # pragma: no cover
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except ImportError:
        # Neither driver present. Fine — only matters if MySQL is configured,
        # and Django will raise a clear error at connection time if it is.
        pass
