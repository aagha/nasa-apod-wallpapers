# nasa-apod-wallpapers

A daily NASA APOD wallpaper list for the
[Projectivy Launcher](https://github.com/spocky/miproja1) Android TV launcher, consumed
through the [Overflight](https://github.com/spocky/projectivy-plugin-wallpaper-overflight)
wallpaper plugin.

`apod.json` is a 100-entry list in Overflight's media format: the 7 newest APOD image days,
then a date-seeded shuffle of the preceding ~200 days. Point Overflight at the raw URL of this
file and it rotates one image per wallpaper refresh.

No API key. The list is built from the keyless
`science.nasa.gov/wp-json/wp/v2/apod-basic` feed; the images are served by NASA's asset CDN.

## Use on the TV

1. Install Projectivy Launcher and the Overflight wallpaper plugin.
2. In Overflight settings, set the media source URL to:

   ```
   https://raw.githubusercontent.com/aagha/nasa-apod-wallpapers/main/apod.json
   ```

3. In Projectivy settings > Appearance > Wallpaper, choose Overflight.

Projectivy keeps the first 100 entries, shuffles them once, and moves to the next one on each
wallpaper refresh (set the refresh interval in Projectivy settings). The list reloads roughly
hourly.

## Rebuild the list

Automated: a GitHub Actions workflow (`.github/workflows/apod.yml`) rebuilds and pushes
`apod.json` daily at 12:17 UTC (04:17 PT). No key or secret is involved. Manual rebuild:

```bash
python3 apod_wallpapers.py --out apod.json --width 1920
git add apod.json && git commit -m "apod: daily rebuild" && git push
```

Options: `--width 3840` for 4K sets, `--count` (default 100), `--newest` (default 7),
`--seed` (defaults to today's date).

## Tests

```bash
python3 -m unittest discover -s tests          # offline
APOD_LIVE=1 python3 -m unittest tests.test_live # live, optional
```

## Notes

- Projectivy ignores anything past the 100th entry, so `apod.json` stays at 100.
- On APOD video days there is no still image; the list skips them.
- `copyright`/`credit` markup is stripped, so the title bar shows plain author text.
