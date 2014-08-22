from django.conf.urls import patterns, url

import views

urlpatterns = patterns('',
    url(r'^old/$', views.index, name='index'),
    url(r'^$', views.main, ),
    url(r'^new/$', views.new, ),
    url(r'^dataset/([0-9]+)/$', views.dataset, ),
    url(r'^dataset/([0-9]+)/(\w+)/$', views.cdrun, ),
   )

