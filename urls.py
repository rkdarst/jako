from django.conf.urls import patterns, url

import views

urlpatterns = patterns('',
    url(r'^old/$', views.index, name='index'),
    url(r'^$', views.main, ),
    url(r'^new/$', views.new, ),
    url(r'^dataset/([0-9]+)/$', views.dataset, ),
    url(r'^dataset/([0-9]+)/(\w+)/$', views.cdrun, ),
    url(r'^dataset/([0-9]+)/(\w+)/(\w+)/$', views.cmtys, ),
    url(r'^dataset/(?P<did>[0-9]+)/(?P<cdname>\w+)/(?P<layer>\w+)/get/(?P<format>\w+)$',
        views.download_cmtys, ),
    url(r'^dataset/(?P<did>[0-9]+)/(?P<cdname>\w+)/(?P<layer>\w+)/viz(?P<ext>[.\w]+)?$',
        views.cmtys_viz, ),
    )

