#!/usr/bin/env python

import glob
import imp
import os
import time
import urllib
import codecs

from cssmin import cssmin
from flask import Markup, g, render_template, request
from slimit import minify
from smartypants import smartypants

import app_config
import copytext

class Includer(object):
    """
    Base class for Javascript and CSS psuedo-template-tags.

    See `make_context` for an explanation of `asset_depth`.
    """
    def __init__(self, asset_depth=0, static_path='', absolute=False):
        self.includes = []
        self.tag_string = None
        self.asset_depth = asset_depth
        self.static_path = static_path
        self.absolute = absolute

    def push(self, path):
        self.includes.append(path)

        return ''

    def _compress(self):
        raise NotImplementedError()

    def _relativize_path(self, path):
        relative_path = path
        depth = len(request.path.split('/')) - (2 + self.asset_depth)

        while depth > 0:
            relative_path = '../%s' % relative_path
            depth -= 1

        return relative_path

    def _absolutize_path(self, path):
        return '%s/%s/%s' % (app_config.S3_BASE_URL, self.static_path, path)

    def render(self, path):
        if self.absolute:
            pather = self._absolutize_path
        else:
            pather = self._relativize_path

        if getattr(g, 'compile_includes', False):
            if path in g.compiled_includes:
                timestamp_path = g.compiled_includes[path]
            else:
                # Add a timestamp to the rendered filename to prevent caching
                timestamp = int(time.time())
                front, back = path.rsplit('.', 1)
                timestamp_path = '%s.%i.%s' % (front, timestamp, back)

                # Delete old rendered versions, just to be tidy
                old_versions = glob.glob('%s/www/%s.*.%s' % (self.static_path, front, back))

                for f in old_versions:
                    os.remove(f)

            out_path = '%s/www/%s' % (self.static_path, timestamp_path)

            if path not in g.compiled_includes:
                print 'Rendering %s' % out_path

                with open(out_path, 'w') as f:
                    f.write(self._compress().encode('utf-8'))

            # See "fab render"
            g.compiled_includes[path] = timestamp_path

            markup = Markup(self.tag_string % pather(timestamp_path))
        else:
            response = ','.join(self.includes)

            response = '\n'.join([
                self.tag_string % pather(src) for src in self.includes
            ])

            markup = Markup(response)

        del self.includes[:]

        return markup

class JavascriptIncluder(Includer):
    """
    Psuedo-template tag that handles collecting Javascript and serving appropriate clean or compressed versions.
    """
    def __init__(self, *args, **kwargs):
        Includer.__init__(self, *args, **kwargs)

        self.tag_string = '<script type="text/javascript" src="%s"></script>'

    def _compress(self):
        output = []
        src_paths = []

        for src in self.includes:
            src_paths.append('www/%s' % src)

            with codecs.open('%s/www/%s' % (self.static_path, src),'r','utf-8') as f:
                print '- compressing %s' % src
                output.append(minify(f.read().encode('utf-8')))

        context = make_context()
        context['paths'] = src_paths

        # header = render_template('_js_header.js', **context)
        # output.insert(0, header)

        return '\n'.join(output)

class CSSIncluder(Includer):
    """
    Psuedo-template tag that handles collecting CSS and serving appropriate clean or compressed versions.
    """
    def __init__(self, *args, **kwargs):
        Includer.__init__(self, *args, **kwargs)

        self.tag_string = '<link rel="stylesheet" type="text/css" href="%s" />'

    def _compress(self):
        output = []

        src_paths = []

        for src in self.includes:

            if src.endswith('less'):
                src_paths.append('%s' % src)
                src = src.replace('less', 'css') # less/example.less -> css/example.css
                src = '%s.less.css' % src[:-4]   # css/example.css -> css/example.less.css
            else:
                src_paths.append('www/%s' % src)

            with codecs.open('%s/www/%s' % (self.static_path, src), encoding='utf-8') as f:
                print '- compressing %s' % src
                output.append(cssmin(f.read().encode('utf-8')))

        context = make_context()
        context['paths'] = src_paths

        # header = render_template('posts/%s/templates/_css_header.css' % self.slug, **context)
        # output.insert(0, header)


        return '\n'.join(output)

def flatten_app_config():
    """
    Returns a copy of app_config containing only
    configuration variables.
    """
    config = {}

    # Only all-caps [constant] vars get included
    for k, v in app_config.__dict__.items():
        if k.upper() == k:
            config[k] = v

    return config

def flatten_post_config(slug):
    """
    Returns a copy of post_config containing only
    configuration variables.
    """
    config = {}


    post_config = imp.load_source('post_config', 'posts/%s/post_config.py' % slug)

    # Only all-caps [constant] vars get included
    for k, v in post_config.__dict__.items():
        if k.upper() == k:
            config[k] = v

    return config

def make_context(asset_depth=2):
    """
    Create a base-context for rendering views.
    Includes app_config and JS/CSS includers.

    `asset_depth` indicates how far into the url hierarchy
    the assets are hosted. If 0, then they are at the root.
    If 1 then at /foo/, etc.
    """
    context = flatten_app_config()

    return context

def urlencode_filter(s):
    """
    Filter to urlencode strings.
    """
    if type(s) == 'Markup':
        s = s.unescape()

    # Evaulate COPY elements
    if type(s) is not unicode:
        s = unicode(s)

    s = s.encode('utf8')
    s = urllib.quote_plus(s)

    return Markup(s)

def smarty_filter(s):
    """
    Filter to smartypants strings.
    """
    if type(s) == 'Markup':
        s = s.unescape()

    # Evaulate COPY elements
    if type(s) is not unicode:
        s = unicode(s)

    s = smartypants(s)

    return Markup(s)

def number_filter(value, fmt="{:,.0f}"):
    """
    Format numbers, default format is integer with commas
    """
    return fmt.format(float(value))
