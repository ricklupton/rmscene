# rmscene

Python library to read v6 files from reMarkable tables (software version 3).

In particular, this version introduces the ability to include text as well as drawn lines. Extracting this text is the original motivation to develop this library, but it also can read much of the other types of data in the reMarkable files.

To convert rm files to other formats, you can use [rmc](https://github.com/ricklupton/rmc), which combines this library with code for converting lines to SVG, PDF, and simple Markdown.

## Changelog

### Unreleased

Breaking changes:

- Rename `scene_items.TextFormat` to `ParagraphStyle` to better describe its
  meaning, now that we have inline bold/italic text styles.
- Remove methods from `scene_items.Text` object; use `text.TextDocument`
  instead.

Other changes:

- Allow empty text items and unknown text formats without throwing exceptions.
- When extra data is present in the file, log the unrecognised bytes at DEBUG
  logging level along with the call stack, to make it easier to figure out where
  the code needs to be modified to read new data.
- Writer: experimental change to emulate different reMarkable software versions
  by passing `{"version": "3.2.2"}` options to `write_blocks`. This allows us to
  continue to test round-trip reading and writing of old test files as new data
  values are added.
- Parse new data values in PageInfoBlock and MigrationInfoBlock.
- Parse text formatting information (bold and italic) introduced in reMarkable
  software version 3.3.

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
