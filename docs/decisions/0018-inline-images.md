# 0018. Images shown in the web

**Date:** 2026-10-19 · **Question:** screenshots attached on the first pilot day opened only as
downloads · **Refines:** decision 0017

On the first pilot day a Team shared screenshots, and each one opened as a download. The author
asked to see attached images right in the Message; previews of documents are a later step.

## Decision

- **Only raster images are shown:** PNG, JPEG, GIF and WebP. The format is recognised by the
  first bytes of the content; the media type the uploader declared is ignored (the plugin
  declares every file as `application/octet-stream`). SVG and every other file are downloaded
  as before: they can carry scripts, and a script served from the instance's origin would run
  with the viewer's session.
- **The format is recognised at upload** and kept with the file (`files.image_type`). A
  migration recognises the files uploaded before this decision from their content on disk.
- **Serving.** A recognised image is served with its own media type, inline; `?download=1`
  serves it as an attachment under its name. Every other file is served as before, as an
  attachment of the opaque type `application/octet-stream`. Every file response carries
  `Content-Security-Policy: default-src 'none'; sandbox` and `X-Content-Type-Options: nosniff`
  besides; Caddy in front of the cloud instance sets the web's policy only on responses that
  carry none, so it does not replace this one.
- **In a Message** the images come under the text, before the other files, reduced to the
  column's width and about 320 px in height, loaded lazily, with the name, the size and a
  download link under each. An image of an extreme shape is cropped to its start instead of
  shrunk to a strip: a tall one (a full-page screenshot) to its top, a wide one to its left. An image larger than a setting (`preview_max_bytes`, 10 MB by
  default) is shown as an ordinary file: without server thumbnails the browser would load it
  whole. An image attached to a Message being written shows a small preview.
- **A click opens the image over the page** in a modal `<dialog>`: the image fits the screen
  and is not enlarged past its natural size; Esc, a click on the backdrop or × closes it; the
  arrows go through the images of the same Message, with "2 / 3" shown; "Open original" opens it
  in a new tab, where it can be zoomed, and "Download" saves it. On a phone the dialog takes the
  whole screen.

## Not now

- Thumbnails made by the server.
- Previews of documents.
- Zoom inside the dialog.

## Why

- Screenshots are the files a Team shares most, and a download per screenshot breaks the
  reading of a Topic.
- Recognising the format by content, not by the declared type, keeps a file that pretends to
  be an image from being served as a page; the sandbox policy is a second line if that check
  is ever wrong.
- A dialog over the page keeps the reader in the Topic; a new tab still covers zooming.
