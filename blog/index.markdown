---
layout: page
title: latest blog entries
section: blog
---

When we start posting to the blog, those entries should show up here.

<ul>
{% for post in site.posts %}
    <li><span>{{ post.date | date_to_string }}</span> &raquo; <a href="{{ site.baseurl }}{{ post.url }}">{{ post.title }}</a></li>
{% endfor %}
</ul>
