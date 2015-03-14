#!/usr/bin/python
import urllib2
from bs4 import BeautifulSoup
from datetime import datetime
import time
import logging as log
log.root.setLevel(log.DEBUG)

import sys

import mysql.connector
from mysql.connector.cursor import MySQLCursorPrepared


if __name__ == '__main__':
    cnx = mysql.connector.connect(db='caps', host='localhost', user='caps', password='caps')
    cnx.set_charset_collation('utf8', 'utf8_general_ci')
    #cursor = cnx.cursor(cursor_class=MySQLCursorPrepared)
    cursor = cnx.cursor()
    stmt = "select * from caps where caps_date = %s"
    cursor.execute(stmt, (sys.argv[1],))
    for c in cursor.fetchall():
        print "{ 'date': '" + str(c[0]) + "', 'author': '" + c[1] + "', 'text': '"+  c[2].replace('\n','<br/>') + "'}"


