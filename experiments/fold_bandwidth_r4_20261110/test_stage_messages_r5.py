import unittest
from stage_messages_r5 import new_messages

class StageMessages(unittest.TestCase):
    def test_does_not_attribute_unsolved_probe_to_analyze(self):
        probe='[error] Script macro error: No trace data'
        complete='[info] Normal completion of simulation'
        self.assertEqual(new_messages([probe],[probe,complete]),[complete])

    def test_same_new_error_is_not_hidden_by_history(self):
        repeated='[error] Repeated error'
        self.assertEqual(new_messages([repeated],[repeated,repeated]),[repeated])

if __name__=='__main__':unittest.main()
