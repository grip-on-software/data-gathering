"""
Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

# pylint: disable=invalid-name

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Data gathering'
project_copyright = '2017-2020 ICTU, 2017-2022 Leiden University, 2017-2024 Leon Helwerda'
author = 'Leon Helwerda'
release = '1.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'myst_parser',
]

myst_heading_anchors = 3

templates_path = ['_templates']
exclude_patterns = []

source_suffix = {'.md': 'markdown'}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
html_copy_source = False
html_use_index = False
html_baseurl = 'https://gros.liacs.nl/data-gathering/'
html_theme_options = {
    'body_max_width': '1146px',
    'page_width': '1366px'
}
