# Data and rights

## Code and media are separate

The repository contains application source, tests and documentation. It does not include movies, posters, downloaded metadata or a populated catalog. Any code license applies only to material the copyright holders have authority to license. It does not grant rights to movies, artwork, trademarks or third-party data.

Only use and distribute media and data when you have the necessary rights. Having a local copy does not establish permission to publish it. Use synthetic titles and original artwork for public tests and screenshots.

## Local data and network requests

The app stores its catalog in `movies.db` under the selected collection root. That database can contain titles, metadata and local filesystem paths. Artwork and thumbnails are stored in movie folders. Treat these files as private and leave them out of issues and releases.

The existing cover-fetch feature sends movie search text to an IMDb suggestion endpoint and downloads images from returned URLs. Those providers receive ordinary network request information, including the requesting IP address. Local browsing does not require cover fetching.

## IMDb restrictions

An accessible endpoint is not proof of permission to extract or redistribute its contents. IMDb restricts automated extraction and provides separate terms for its datasets. Do not assume the existing cover-fetch implementation is authorized for your use or that attribution makes redistribution permissible. Confirm permission or use artwork you have rights to supply locally before relying on this feature.

Official references

- [IMDb conditions of use](https://www.imdb.com/conditions/)
- [IMDb data use in software](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX)

## License status

Original project code is available under the [MIT License](LICENSE), with credit to Peter-206 through the required copyright and license notices. Commercial use is allowed without contacting the author. The license does not require a visible credit screen or endorsement.

This document records project behavior and unresolved rights questions. It does not certify legal compliance.
