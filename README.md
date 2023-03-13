# rmscene

Python library to read v6 files from reMarkable tables (software version 3).

In particular, this version introduces the ability to include text as well as drawn lines. Extracting this text is the original motivation to develop this library, but it also can read much of the other types of data in the reMarkable files.

To convert rm files to other formats, you can use [rmc](https://github.com/ricklupton/rmc), which combines this library with code for converting lines to SVG, PDF, and simple Markdown.

## Changelog

### v0.3.0

- Introduce `CrdtSequence` type to handle the different places that CRDT
  sequences are used, not just for text.
- Introduce `scene_items` module with data structures representing the data,
  independently from the `Block`s used to serialize them to `.rm` files.
- Introduce a `SceneTree` structure which holds the `SceneItem`s in
  groups/layers.
- Move Text data from `RootTextBlock` to `scene_items.Text` class, which
  includes methods for extracting lines of text and formatting.
- Text lines now include the trailing newline character.
- Read `GlyphRange` scene items, representing highlighted text in PDFs.

### v0.2.0

- Try to be more robust to unexpected data introduced by newer reMarkable software versions.
- Only warn once if unknown data is present, rather than for every block.
- Small API change to return type of `read_block` and `read_subblock` methods.

### v0.1.0

- Initial release

## Acknowledgements

https://github.com/ddvk/reader helped a lot in figuring out the structure and meaning of the files.
