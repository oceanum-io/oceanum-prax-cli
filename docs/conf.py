# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'oceanum-prax'
copyright = '2025, Oceanum Developers'
author = 'Oceanum Developers'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinxcontrib.autodoc_pydantic",
    "sphinxcontrib.programoutput",    
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


html_theme_options = {
    "collapse_navigation": False,
    "show_nav_level": 2,
    "secondary_sidebar_items": ["page-toc", "edit-this-page", "sourcelink"],
    "logo": {
      "image_light": "oceanum-secondary-logo-marine-rgb.svg",
      "image_dark": "oceanum-secondary-logo-powder-blue-rgb.svg",
    },
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/oceanum-io/oceanum-prax-cli",
            "icon": "fab fa-github",
            "type": "fontawesome",
        }
    ],
}

html_sidebars = {
    "**": ["globaltoc.html"],
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']
