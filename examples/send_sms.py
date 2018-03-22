#!/usr/bin/env python3

import logging
import esme, event_loop

# if you want to know what's happening inside python-smpplib
logging.basicConfig(level='DEBUG')

e = esme.Esme('6789')
e.set_system_id('myesme')
e.set_password('')
e.connect('127.0.0.1', 2775)
msg = "Test"
dst_msisdn="777"

logging.info("Sending message %s to %s" % (msg, dst_msisdn))
umref = e.sms_send_wait_resp(msg, dst_msisdn, e.MSGMODE_STOREFORWARD, receipt=True)
logging.info('Waiting to receive and consume sms receipt with reference %s' % umref)
event_loop.wait(e.receipt_was_received, umref)
