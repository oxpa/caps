#!/usr/bin/python
import urllib2
from bs4 import BeautifulSoup
from datetime import datetime,date,timedelta
import time
import logging as log

import sys
import argparse

import MySQLdb



def getCapsByDate(date, args):
    phrase = ''
    time=''
    author=''
    log.debug(args.base + args.conference + '/' + date + '.html')
    response = urllib2.urlopen(args.base + args.conference + '/' + date + '.html')
    soup = BeautifulSoup(response.read())
    elem=soup.find('a',attrs={'class':'ts'})
    caps=[]

    while elem:
        # just 'is a timestamp' condition
        if hasattr(elem,'name') and elem.name == 'a' \
            and hasattr(elem, 'attrs') \
            and'name' in elem.attrs and 'id' in elem.attrs \
            and elem.attrs['name'] == elem.attrs['id']:

            # if there is a phrase parsed out - remember it
            if phrase.isupper() and phrase.count('\n') >1:
                caps.append({'time':time, 'author':author, 'phrase':phrase})
                log.debug("TIME: %s, AUTHOR: %s, PHRASE: %s", time,  author, phrase.strip())

            phrase = ''
            # remeber new timestamp
            # transform a string like '10:40:00.545496' into an integer time:
            dtime = datetime.strptime(date + elem.attrs['id'], '%Y/%m/%d%X.%f')
            time = dtime.strftime('%s') + dtime.strftime('%f')
    
        else:
            # not a timestamp, try getting CAPS out of elements before next timestamp occur
            if hasattr(elem,'name') and elem.name == 'font' and 'class' in elem.attrs and 'mn' in elem.attrs['class']:
                author = elem.text[1:-1]
            elif hasattr(elem,'name') and elem.name == 'br':
                # don't add \n in front of a phrase
                if phrase != '':
                    phrase = phrase + '\n'
            elif hasattr(elem,'text'):
                phrase = phrase + elem.text.replace('|','\n')
            elif elem == '\n' or elem == '\r':
                pass
            else: 
                # skip nicks in front of a CAPS
                if phrase == '' and elem.strip(' \n\r\t').endswith(':') and not elem.isupper():
                    log.debug('skipping an element "%s"', elem)
                    pass
                # don't add spaces in front of a phrase
                elif not (elem.isspace() and phrase == ''):
                    phrase = phrase + elem.replace('|', '\n')
        elem = elem.next_sibling

    if phrase.isupper() and phrase.count('\n') >1:
        caps.append({'time':time, 'author':author, 'phrase':phrase})
        log.debug("TIME: %s, AUTHOR: %s, PHRASE: %s", time,  author, phrase.strip())
    
    log.debug('%s previously: %s caps, found %s caps'%(date, getCapsByDate.counter, len(caps)))
    getCapsByDate.counter += len(caps)
    return caps
        
            
def store_caps(args):

    db=MySQLdb.connect(host=args.host, user=args.user, passwd=args.password, db=args.database, use_unicode=True, charset='utf8')
    cursor = db.cursor()
    stmt = "select conference_id from conferences where conference_name = %s limit 1"
    result = cursor.execute(stmt, (args.conference,))
    if result > 1:
        exit(1)
    elif result == 1:
        cf_id = cursor.fetchone()[0]
        log.debug('conference id is %s' % cf_id)
    elif result == 0:
        stmt = "insert into conferences (conference_name) values (%s)"
        cursor.execute(stmt, (args.conference,))
        stmt = "select last_insert_id()"
        cursor.execute(stmt)
        cf_id = cursor.fetchone()[0] 
    else:
        exit(2)

    update_stats_stmt = """insert into confstats (cstats_totalcaps, cstats_confid, cstats_mindate, cstats_maxdate) 
                                        select count(*) as cstats_totalcaps, caps_conference, %s as cstats_mindate, %s as cstats_maxdate  
                                            from caps 
                                            where caps_conference = %s 
               ON DUPLICATE KEY UPDATE
                cstats_totalcaps = VALUES(cstats_totalcaps)
                , cstats_mindate = LEAST(cstats_mindate, VALUES(cstats_mindate))
                , cstats_maxdate = GREATEST(cstats_maxdate, VALUES(cstats_maxdate)) """

    insert_caps_stmt = "insert into caps (caps_date, caps_author, caps_text, caps_conference) values (%s, %s, %s, %s)"
    if args.force:
        insert_caps_stmt += " on duplicate key update caps_text=VALUES(caps_text)"
    dates = get_log_dates(args)
    
    getCapsByDate.counter = 0;
    for d in dates:
        if check_date(args, db, d, cf_id):
            log.debug('getting for %s', d)
            #from time import sleep; sleep(1)
            for i in getCapsByDate(d, args):
                if args.do_nothing:
                    log.info("Would store %s", i)
                    continue
                try:
                    cursor.execute(insert_caps_stmt, (i.get('time'), i.get('author').encode('utf-8'), i.get('phrase').strip().encode('utf-8'), cf_id))
                except Exception as e:
                    log.critical('%s', ('on', insert_caps_stmt %( str(i.get('time')), i.get('author'), i.get('phrase').strip(), cf_id), 'execution an error occured:', e))
                    exit(5)
                try:
                    cursor.execute(update_stats_stmt, ( i.get('time'), i.get('time'), cf_id ))
                except Exception as e:
                    log.critical('%s', ('on', update_stats_stmt %( cf_id, str(i.get('time')), str(i.get('time')), ), 'execution an error occured:', e))
                    exit(5)

        else:
            log.debug('not storing for %s', d)
        db.commit()

def get_log_dates(args):

    if args.date:
        args.date.sort()
        dates = args.date
    elif 'full' in args:
        response = urllib2.urlopen(args.base + args.conference )
        years = [ i.split('"')[1] for i in response.readlines() if 'href="' in i and '..' not in i ]
        response.close()
        dates = []
        for year in years:
            response = urllib2.urlopen(args.base + args.conference + '/' + year )
            months = [ i.split('"')[1] for i in response.readlines() if 'href="' in i and '..' not in i ]
            response.close()
            for month in months:
                response = urllib2.urlopen(args.base + args.conference + '/' + year + month)
                days = [ i.split('"')[1] for i in response.readlines() if 'href="' in i and '..' not in i ]
                response.close()
                for day in days:
                    dates.append('%s%s%s'%(year, month, day.split('.')[0]))
    else:
        exit(4) #no cron, full, yesterday or date option
    #log.debug('returning dates: %s', dates);
    dates.reverse()
    return dates

def check_date(args, db, date, cf_id):
    if args.force:
        return True
    check_date_stmt = "select 1 from confstats where  (%s > cstats_maxdate or %s < cstats_mindate) and cstats_confid = %s limit 1"
    dtime = datetime.strptime(date, '%Y/%m/%d')
    time = dtime.strftime('%s') + dtime.strftime('%f')
    cursor = db.cursor() 
    result = cursor.execute(check_date_stmt, (time, int(time) + 24*60*60*1000000, cf_id))
    if result == 1:
        cursor.fetchall()
        #log.debug('date check successfull')
        return True
    #log.debug('returning false date check')
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='fetches CAPS lines from a conference log at '+
            'chatlogs.jabber.ru and stores them into a database')
    parser.add_argument('--conference', '-c', help="a conference name to look through", 
                        default='programming@conference.jabber.ru')
    parser.add_argument('--force', '-f', help="force processing even if there are entries"+
                        " in a DB for this date", action='store_true')
    parser.add_argument('--base', help="base url to search for caps", default="http://chatlogs.jabber.ru/")
    parser.add_argument('--database', help="database name to store caps", default="caps")
    parser.add_argument('--host', help="database server host", default="localhost")
    parser.add_argument('--port', help="database server port", default="3306")
    parser.add_argument('--user', help="database server user", default="caps")
    parser.add_argument('--password', help="database server password", default="caps")
    parser.add_argument('--do-nothing', help="Don't store anything. Just fetch, parse and show", action="store_true")
    parser.add_argument('--debug', help="Add some extensive logging", action="store_true")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--date', '-d', help="parse specific date.Format is: '%%Y/%%m/%%d' (as in a url)", action="append")
    group.add_argument('--yesterday', '--cron', '-y', dest="date", help="Parse yesterdays log", action='store_const', 
                        const=[datetime.strftime(date.today() - timedelta(1),"%Y/%m/%d")])
    group.add_argument('--full', help="Initial parsing of a conference", action="store_true")


    args=parser.parse_args(sys.argv[1:])
    if 'help' in args:
        parser.print_help()
    else:
        if 'debug' in args and args.debug:
            log.root.setLevel(log.DEBUG)
        
        log.debug(args) 
        store_caps(args)

