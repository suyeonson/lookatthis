#!/usr/bin/env python

import argparse
import copytext
from glob import glob
import imp
import json

from flask import Blueprint, Flask, render_template, render_template_string, url_for

import app_config
from render_utils import make_context, smarty_filter, urlencode_filter, CSSIncluder, JavascriptIncluder
import static
import static_post
import static_theme

app = Flask(__name__)

app.jinja_env.filters['smarty'] = smarty_filter
app.jinja_env.filters['urlencode'] = urlencode_filter

posts = Blueprint('posts', __name__, template_folder='posts/')

# Example application views
@app.route('/')
def _posts_list():
    """
    Renders a list of all posts for local testing.
    """
    context = make_context()
    context['posts'] = []

    posts = glob('%s/*' % app_config.POST_PATH)
    for post in posts:
        name = post.split('%s/' % app_config.POST_PATH)[1]
        context['posts'].append(name)

    context['posts_count'] = len(context['posts'])

    return render_template('post_list.html', **context)

@posts.route('/posts/<slug>/')
def _post(slug):
    """
    Renders a post without the tumblr wrapper.
    """

    post_path = '%s/%s' % (app_config.POST_PATH, slug)

    context = make_context()
    context['slug'] = slug
    context['COPY'] = copytext.Copy(filename='data/%s.xlsx' % slug)

    context['JS'] = JavascriptIncluder(asset_depth=2, static_path=post_path)
    context['CSS'] = CSSIncluder(asset_depth=2, static_path=post_path)

    try:
        post_config = imp.load_source('post_config', '%s/post_config.py' % post_path)
        context.update(post_config.__dict__)
    except IOError:
        pass

    dt = app_config.DEPLOYMENT_TARGET

    if dt and post_config.TARGET_IDS[dt] and post_config.IS_PUBLISHED[dt]:

        context['post_id'] = post_config.TARGET_IDS[dt]
        context['tumblr_name'] = app_config.TUMBLR_NAME

    with open('data/featured.json') as f:
        context['featured'] = json.load(f)

    with open('%s/templates/index.html' % post_path) as f:
        template = f.read().decode('utf-8')

    return render_template_string(template, **context)

@app.route('/posts/<slug>/preview')
def _post_preview(slug):
    """
    Renders a post with the Tumblr wrapper.
    """
    context = make_context()
    context['slug'] = slug

    return render_template('parent.html', **context)

app.register_blueprint(static.static)
app.register_blueprint(posts)
app.register_blueprint(static_post.post)
app.register_blueprint(static_theme.theme)

# Boilerplate
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port')
    args = parser.parse_args()
    server_port = 8000

    if args.port:
        server_port = int(args.port)

    app.run(host='0.0.0.0', port=server_port, debug=app_config.DEBUG)
