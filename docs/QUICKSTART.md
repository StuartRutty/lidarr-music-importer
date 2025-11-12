# Quickstart

This quickstart shows the minimal steps to get the Lidarr Music Importer running and import a small CSV sample.

1) Install dependencies

Windows (cmd.exe / PowerShell):

```powershell
py -3 -m pip install -r requirements.txt
```

2) Create your configuration

Copy the template and edit `config.py`:

Windows (cmd.exe):

```
copy config.template.py config.py
```

PowerShell:

```powershell
Copy-Item -Path .\config.template.py -Destination .\config.py
```

macOS / Linux:

```bash
cp config.template.py config.py
```

Open `config.py` and fill in your Lidarr URL, API key, and other settings.

3) Run a quick parse (dry run)

Use the universal parser to parse a CSV into a cleaned output file:

```powershell
py -3 scripts/universal_parser.py examples/example_albums.csv -o parsed_example.csv --verbose --max-items 10
```

4) Add parsed items to Lidarr

Once you are happy with parsing, use the `add_albums_to_lidarr.py` script to add albums to your configured Lidarr instance.

```powershell
py -3 scripts/add_albums_to_lidarr.py parsed_example.csv --dry-run
```

Remove `--dry-run` when you're ready to actually add albums.

5) Tests

Run the project's test suite:

```powershell
py -3 -m pytest -q
```

Where to go next

- Full usage and production guidance: see `docs/USAGE_AND_PRODUCTION.md`
- Parser internals and enhanced MusicBrainz search: see `docs/UNIVERSAL_PARSER.md`

If you want, I can add a short example CSV and a prefilled `config.example.py` (not containing secrets) to speed onboarding.
