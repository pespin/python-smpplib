RuntimeError#!/usr/bin/env python3


import smpplib.gsm
import smpplib.client
import smpplib.command
import smpplib.consts
import smpplib.exceptions
import logging

import event_loop

MAX_SYS_ID_LEN = 16
MAX_PASSWD_LEN = 16

class Esme:
    client = None
    listening = None
    bound = None
    connected = None

    MSGMODE_TRANSACTION = smpplib.consts.SMPP_MSGMODE_FORWARD
    MSGMODE_STOREFORWARD = smpplib.consts.SMPP_MSGMODE_STOREFORWARD

    def __init__(self, msisdn):
        self.msisdn = msisdn
        # Get last characters of msisdn to stay inside MAX_SYS_ID_LEN. Similar to modulus operator.
        self.set_system_id('esme-' + self.msisdn[-11:])
        self.set_password('esme-pwd')
        self.connected = False
        self.bound = False
        self.listening = False
        self.references_pending_receipt = []
        self.next_user_message_reference = 1

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        try:
            self.disconnect()
        except smpplib.exceptions.ConnectionError:
            pass

    def set_system_id(self, name):
        if len(name) > MAX_SYS_ID_LEN:
            raise RuntimeError('Esme system_id too long! %d vs %d', len(name), MAX_SYS_ID_LEN)
        self.system_id = name

    def set_password(self, password):
        if len(password) > MAX_PASSWD_LEN:
            raise RuntimeError('Esme password too long! %d vs %d', len(password), MAX_PASSWD_LEN)
        self.password = password

    def poll(self):
        self.client.poll()

    def start_listening(self):
        self.listening = True
        event_loop.register_poll_func(self.poll)

    def stop_listening(self):
        if not self.listening:
            return
        self.listening = False
        # Empty the queue before processing the unbind + disconnect PDUs
        event_loop.unregister_poll_func(self.poll)
        self.poll()

    def connect(self, host, port):
        if self.client:
            self.disconnect()
        self.client = smpplib.client.Client(host, port, timeout=None)
        self.client.set_message_sent_handler(
            lambda pdu: logging.debug('Unhandled submit_sm_resp message:', pdu.sequence) )
        self.client.set_message_received_handler(self._message_received_handler)
        self.client.connect()
        self.connected = True
        self.client.bind_transceiver(system_id=self.system_id, password=self.password)
        self.bound = True
        logging.info('Connected and bound successfully to %s (%s:%d). Starting to listen.' % (self.system_id, host, port))
        self.start_listening()

    def disconnect(self):
        self.stop_listening()
        if self.bound:
            self.client.unbind()
            self.bound = False
        if self.connected:
            self.client.disconnect()
            self.connected = False

    def _message_received_handler(self, pdu, *args):
        logging.debug('message received: %r' % repr(pdu.sequence))
        if isinstance(pdu, smpplib.command.AlertNotification):
            logging.debug('message received:  AlertNotification: %r' % repr(pdu.ms_availability_status))
        elif isinstance(pdu, smpplib.command.DeliverSM):
            umref = int(pdu.user_message_reference)
            logging.debug('message received: DeliverSM %r %r' % (repr(self.references_pending_receipt), repr(umref)))
            self.references_pending_receipt.remove(umref)

    def receipt_was_received(self, umref):
        return umref not in self.references_pending_receipt

    def run_method_expect_failure(self, errcode, method, *args):
        try:
            method(*args)
            #it should not succeed, raise an exception:
            raise RuntimeError('SMPP Failure: %s should have failed with SMPP error %d (%s) but succeeded.' % (method, errcode, smpplib.consts.DESCRIPTIONS[errcode]))
        except smpplib.exceptions.PDUError as e:
            if e.args[1] != errcode:
                raise e
            logging.debug('Expected failure triggered: %d' % errcode)

    def sms_send(self, sms, dst_msisdn, mode, receipt=False):
        parts, encoding_flag, msg_type_flag = smpplib.gsm.make_parts(sms)
        seqs = []
        logging.info('Sending SMS "%s" to %s' % (sms, dst_msisdn))
        umref = self.next_user_message_reference
        self.next_user_message_reference = (self.next_user_message_reference + 1) % (1 << 8)
        for part in parts:
            pdu = self.client.send_message(
                source_addr_ton=smpplib.consts.SMPP_TON_INTL,
                source_addr_npi=smpplib.consts.SMPP_NPI_ISDN,
                source_addr=self.msisdn,
                dest_addr_ton=smpplib.consts.SMPP_TON_INTL,
                dest_addr_npi=smpplib.consts.SMPP_NPI_ISDN,
                destination_addr=dst_msisdn,
                short_message=part,
                data_coding=encoding_flag,
                esm_class=mode,
                registered_delivery=receipt,
                user_message_reference=umref,
                )

            logging.debug('sent part with seq %s' % pdu.sequence)
            seqs.append(pdu.sequence)
        if receipt:
            self.references_pending_receipt.append(umref)
        return umref, seqs

    def _process_pdus_pending(self, pdu, **kwargs):
        logging.debug('message sent resp with seq %s, pdus_pending: %s' % (pdu.sequence, self.pdus_pending))
        if pdu.sequence in self.pdus_pending:
            self.pdus_pending.remove(pdu.sequence)

    def sms_send_wait_resp(self, sms, dst_msisdn, mode, receipt=False):
        old_func = self.client.message_sent_handler
        try:
            umref, self.pdus_pending = self.sms_send(sms, dst_msisdn, mode, receipt)
            logging.debug('pdus_pending: %s' % self.pdus_pending)
            self.client.set_message_sent_handler(self._process_pdus_pending)
            event_loop.wait(lambda: len(self.pdus_pending) == 0, timeout=10)
            return umref
        finally:
            self.client.set_message_sent_handler(old_func)
