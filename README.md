# rmscene

Python library to read v6 files from reMarkable tables (software version 3).

In particular, this version introduces the ability to include text as well as drawn lines. Extracting this text is the original motivation to develop this library, but it also can read much of the other types of data in the reMarkable files.

To convert rm files to other formats, you can use [rmc](https://github.com/ricklupton/rmc), which combines this library with code for converting lines to SVG, PDF, and simple Markdown.

## Acknowledgements

https://github.com/ddvk/reader helped a lot in figuring out the structure and meaning of the files.
