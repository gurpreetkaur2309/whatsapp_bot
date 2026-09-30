"""DATABASE_URL parsing for hosted providers.

Each managed MySQL host hands you a slightly different URL. django-environ
passes every query-string parameter straight into OPTIONS, and OPTIONS become
keyword arguments to the driver's connect() — so a stray `ssl-mode` key raises
TypeError at the first query, which looks nothing like a config problem.
"""

import importlib

from django.test import SimpleTestCase


def parse(url, **env_overrides):
    """Re-evaluate the DATABASE_URL branch of settings.py in isolation."""
    import environ

    env = environ.Env()
    config = env.db_url_config(url)
    options = config.setdefault("OPTIONS", {})

    ssl_hint = options.pop("ssl-mode", None) or options.pop("sslmode", None)
    options["charset"] = "utf8mb4"
    require = env_overrides.get(
        "DB_REQUIRE_SSL",
        str(ssl_hint).upper() in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"},
    )
    if require:
        options["ssl"] = {"ssl_mode": "REQUIRED"}
    else:
        options.pop("ssl", None)
    for key in [k for k in options if "-" in k]:
        options.pop(key)
    return config


class DatabaseUrlTests(SimpleTestCase):
    AIVEN = "mysql://avnadmin:pw@mysql-abc.h.aivencloud.com:23456/defaultdb?ssl-mode=REQUIRED"
    RAILWAY = "mysql://root:pw@centerbeam.proxy.rlwy.net:37421/railway"
    TIDB = "mysql://abc.root:pw@gateway01.prod.aws.tidbcloud.com:4000/test"

    def test_aiven_url_resolves_to_the_mysql_backend(self):
        config = parse(self.AIVEN)
        self.assertEqual(config["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(config["NAME"], "defaultdb")
        self.assertEqual(config["HOST"], "mysql-abc.h.aivencloud.com")
        self.assertEqual(config["PORT"], 23456)

    def test_aiven_ssl_mode_becomes_a_driver_safe_ssl_dict(self):
        options = parse(self.AIVEN)["OPTIONS"]
        self.assertEqual(options["ssl"], {"ssl_mode": "REQUIRED"})
        self.assertNotIn("ssl-mode", options)

    def test_no_option_key_contains_a_hyphen(self):
        """A hyphenated key can never be a valid connect() kwarg."""
        for url in (self.AIVEN, self.RAILWAY, self.TIDB):
            with self.subTest(url=url):
                options = parse(url)["OPTIONS"]
                self.assertEqual([k for k in options if "-" in k], [])

    def test_railway_defaults_to_no_ssl(self):
        # Railway's TCP proxy does not terminate TLS.
        options = parse(self.RAILWAY)["OPTIONS"]
        self.assertNotIn("ssl", options)

    def test_ssl_can_be_forced_off_for_a_provider_that_advertises_it(self):
        options = parse(self.AIVEN, DB_REQUIRE_SSL=False)["OPTIONS"]
        self.assertNotIn("ssl", options)

    def test_ssl_can_be_forced_on(self):
        options = parse(self.RAILWAY, DB_REQUIRE_SSL=True)["OPTIONS"]
        self.assertEqual(options["ssl"], {"ssl_mode": "REQUIRED"})

    def test_charset_is_always_utf8mb4(self):
        for url in (self.AIVEN, self.RAILWAY, self.TIDB):
            self.assertEqual(parse(url)["OPTIONS"]["charset"], "utf8mb4")

    def test_postgres_url_still_works(self):
        config = parse("postgres://u:p@ep-cool.neon.tech:5432/neondb")
        self.assertIn("postgresql", config["ENGINE"])
