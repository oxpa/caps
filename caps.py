#!/usr//bin/python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/usr/lib/python2.6/site-packages/Jinja2-2.6-py2.6.egg')

import mysql.connector

import MySQLdb

from datetime import datetime
from flask import json, redirect, url_for, jsonify, Response, request, render_template

from flask import Flask
app = Flask(__name__)
#app.debug=True
app.debug=False
import logging
log=app.logger

#app.config['SERVER_NAME'] = '172.16.172.3'

#@app.errorhandler(404)
#def page_not_found(error):
#    return redirect(url_for('show_caps', page=0, page_size=10))


def get_caps(page=None, page_size=10, db='caps', host='localhost', user='caps', pwd='caps', cf_id = 1):
    db=MySQLdb.connect(host=host, user=user, passwd=pwd, db=db, use_unicode=True, charset='utf8')
    c=db.cursor()
    stmt = "select caps_date, caps_author, caps_text from caps where caps_conference = %s order by caps_date asc limit %s, %s"
    pre_stmt = "select cstats_totalcaps div %s, cstats_totalcaps mod %s + %s from confstats where cstats_confid = %s"
    c.execute(pre_stmt,(page_size, page_size, page_size, cf_id))
    log.debug(pre_stmt, page_size, page_size, page_size, cf_id)
    ((total_pages, limit_size),) = c.fetchall()
    if page is None or page == total_pages:
        limit_start = (total_pages - 1) * page_size
        #limit_size is unchanged
    else:
        limit_start = (page - 1) * page_size 
        limit_size = page_size 
    
    log.debug("limit start is %s, limit size is %s", limit_start, limit_size)

    c.execute(stmt, (cf_id, limit_start, limit_size))
    rval = [ {'date':i[0]/1000, 'us': ('%03d'%(i[0]%1000)).rstrip('0') ,  'author':i[1], 'text':i[2].replace('\n', '<br/>')} for i in c.fetchall() ]
    rval.reverse()
    return {'pagestotal':total_pages, 'caps':rval }

def get_caps_by_date(date=None, db='caps', host='localhost', user='caps', pwd='caps', cf_id = 1):
    if date == None:
        return None

    db=MySQLdb.connect(host=host, user=user, passwd=pwd, db=db, use_unicode=True, charset='utf8')
    c=db.cursor()
    stmt = "select caps_date, caps_author, caps_text, twitter_nick from caps left join authors on caps_author = authors_nick left join twitter on author_real_id = authors_real_id where caps_conference = %s and caps_date like %s limit 1"
    #stmt = "select caps_date, caps_author, caps_text, coalesce(twitter_nick, caps_author) from caps join authors on caps_author = authors_nick left join twitter on author_real_id = authors_real_id where caps_conference = %s and caps_date like %s limit 1"
    pre_stmt = "select cstats_totalcaps div %s, cstats_totalcaps mod %s + %s from confstats where cstats_confid = %s"
    page_size = 10
    c.execute(pre_stmt,(page_size, page_size, page_size, cf_id))
    ((total_pages, limit_size),) = c.fetchall()
    log.debug('date is %s', date)
    c.execute(stmt, (cf_id, '%s%%'%date))

    rval = [ {'date':i[0]/1000, 'us': ('%03d'%(i[0]%1000)).rstrip('0') ,  'author':i[1], 'text':i[2].replace('\n', '<br/>'), 'twauthor':i[3]} for i in c.fetchall() ]
    rval.reverse()
    return {'pagestotal':total_pages, 'caps':rval }

@app.route('/items/<int:date>/')
@app.route('/se/items/<int:date>/')
def show_caps_by_date(date):
    log.debug('showing caps %s', date)
    caps = get_caps_by_date(date)
    if caps is None:
        return redirect(url_for('show_caps', page=None, page_size=10))
    else:
        if '_escaped_fragment_' in request.args or '/se/' in request.url_rule.rule:
            log.info("Looks like a bot came to my page")
            return render_template('caps.tmpl', caps=caps, dt=datetime, page=caps['pagestotal'])
        return Response(json.dumps(caps, ensure_ascii=False),  content_type='application/json; charset=utf-8')
        

@app.route('/')
@app.route('/<int:page>/' )
@app.route('/<int:page>/<int:page_size>/')
@app.route('/se/')
@app.route('/se/<int:page>/' )
@app.route('/se/<int:page>/<int:page_size>/')

def show_caps(page=None, page_size=10):
    log.debug("page is %s, size is %s", page, page_size)
    if not isinstance(page, int) or page < 1:
        page = None
    if not isinstance(page_size, int) or page_size < 1:
        page_size = 10
    caps = get_caps(page = page,  page_size=page_size)
    if '_escaped_fragment_' in request.args or '/se/' in request.url_rule.rule:
        log.debug("looks like a bot requesting my page")
        if page == None:
            page = caps['pagestotal']
        return render_template('caps.tmpl', caps=caps, dt=datetime, page=page)
    else:
        log.debug('useragent is %s, rule is %s', request.user_agent.string, request.url_rule.rule)
        return Response(json.dumps(caps, ensure_ascii=False),  content_type='application/json; charset=utf-8')

if __name__ == '__main__':
    app.config['SERVER_NAME'] = 'localhost:5000'
    app.run(debug=True)
    
