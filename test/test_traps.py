# from unittest import TestCase
# from unittest.mock import MagicMock, patch
#
# mock_config = """usernameSecrets:
#   - sc4snmp-homesecure-sha-des2"""
#
#
# @patch('splunk_connect_for_snmp.snmp.manager.Poller.__init__')
# class TestTraps(TestCase):
#     @patch('opentelemetry.instrumentation.celery.CeleryInstrumentor.instrument')
#     @patch('opentelemetry.instrumentation.logging.LoggingInstrumentor.instrument')
#     def test_init_celery_tracing(self, m_instr1, m_instr2, m_init):
#         m_init.return_value = None
#         from splunk_connect_for_snmp.traps import init_celery_tracing
#         init_celery_tracing()
#         m_instr1.assert_called()
#         m_instr2.assert_called()
#
#     @patch('opentelemetry.instrumentation.celery.CeleryInstrumentor.instrument')
#     @patch('opentelemetry.instrumentation.logging.LoggingInstrumentor.instrument')
#     def test_init_celery_beat_tracing(self, m_instr1, m_instr2, m_init):
#         m_init.return_value = None
#         from splunk_connect_for_snmp.traps import init_celery_beat_tracing
#         init_celery_beat_tracing()
#         m_instr1.assert_called()
#         m_instr2.assert_called()
#
#     def test_setup_task_logger(self, m_init):
#         m_init.return_value = None
#         from splunk_connect_for_snmp.traps import setup_task_logger
#         logger = MagicMock()
#         handler1 = MagicMock()
#         handler2 = MagicMock()
#         logger.handlers = [handler1, handler2]
#         setup_task_logger(logger)
#
#         handler1.setFormatter.assert_called()
#         handler2.setFormatter.assert_called()
#
#     # @patch('asyncio.new_event_loop')
#     # @patch('asyncio.set_event_loop')
#     # @patch('pysnmp.entity.engine.SnmpEngine')
#     # @patch('pysnmp.entity.config.addTransport')
#     # @patch('pysnmp.entity.config.addV3User')
#     # @patch('builtins.open', new_callable=mock_open, read_data=mock_config)
#     # @patch('splunk_connect_for_snmp.traps.get_secret_value')
#     # @patch('splunk_connect_for_snmp.snmp.manager.Poller.__init__')
#     # def test_main(self, m_init, m_secret, m_open, m_add_v3_user, m_add_transport, m_engine, m_set_loop, m_loop):
#     #     m_init.return_value = MagicMock()
#     #     my_loop = MagicMock()
#     #     m_engine.return_value = MagicMock()
#     #     m_secret.side_effect = ["secret1", "secret2", "secret3", "SHA224", "AES192BLMT", "1", "2"]
#     #     m_loop.return_value = my_loop
#     #
#     #     main()
#     #     m_add_v3_user.assert_called()
#     #     m_add_transport.assert_called()
#     #     my_loop.run_forever.assert_called()
