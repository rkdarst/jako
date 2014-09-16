from django.conf.urls import patterns, url

import views

urlpatterns = patterns('',
    url(r'^$', views.main, ),
    url(r'^new/$', views.new, ),
    url(r'^dataset/([0-9]+)/$', views.dataset, ),
    url(r'^dataset/([0-9]+)/(\w+)/$', views.cdrun, ),
    url(r'^dataset/([0-9]+)/(\w+)/(\w+)/$', views.cmtys, ),
    url(r'^dataset/(?P<did>[0-9]+)/(?P<cdname>\w+)/(?P<layer>\w+)/get/(?P<format>\S+)$',
        views.download_cmtys, ),
    url(r'^dataset/(?P<did>[0-9]+)/(?P<cdname>\w+)/(?P<layer>\w+)/viz(?P<ext>[.\w]+)?$',
        views.cmtys_viz, ),
    url(r'^dataset/(?P<did>[0-9]+)/(?P<cdname>\w+)/stdout$',
        views.cmtys_stdout, ),


    url(r'^about/$','cd20.flatpages.view_flat', dict(pagename='about'),
                   name='jako-about'),
    )

