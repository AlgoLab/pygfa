import sys
sys.path.insert(0, '../')

import copy
import unittest
import logging

import pygfa

logging.basicConfig(level=logging.DEBUG)

gfa_file = "H\tac:Z:test2\n" + "H\tVN:Z:1.0\n" + "H\taa:i:12\tab:Z:test1\n" \
  + "H\taa:i:15\n" + "S\t1\t*\n" + "S\t2\tGGAGGTAGCTAG\n" + "S\t3\tAGGATCTTATTTA\n" \
  + "S\t4\tATTAGGGCCGGTAA\n" + "S\t5\tGTAGGAGGTACG\n" + "S\t6\tCTAGACCAG\n" \
  + "S\t8\t*\n" + "S\t23\tTTTGGCCGGAAAATTAG\n" + "S\t10\tGTCCAGTGATC\n" \
  + "S\t11\tACTGGACTAGGTA\n" + "S\t14\t*\n" + "S\t15\tAGGTAGCTACCAGTA\n" \
  + "S\t9\t*\n" + "S\t18\t*\n" + "S\t0\t*\n" + "S\t7\tTACGGTTGAAT\n" \
  + "S\t12\tGTGGGACATT\n" + "S\t13\t*\n" +"L\t1\t+\t2\t+\t5M\tID:Z:1_to_2\n" \
  + "L\t1\t+\t3\t+\t3M\tID:Z:1_to_3\n" + "L\t1\t+\t5\t+\t8M\tID:Z:1_to_5\n" \
  + "L\t2\t+\t6\t+\t4M\tID:Z:2_to_6\n" + "L\t3\t+\t4\t-\t3M\tID:Z:3_to_4\n" \
  + "L\t4\t-\t23\t-\t5M\tID:Z:4_to_23\n" + "L\t5\t-\t8\t+\t5M\tID:Z:5_to_8\n" \
  + "L\t10\t-\t11\t+\t7M\tID:Z:10_to_11\n" + "L\t11\t+\t14\t+\t3M\tID:Z:11_to_14\n" \
  + "L\t11\t+\t15\t+\t5M\tID:Z:11_to_15\n" + "L\t9\t+\t18\t-\t3M\tID:Z:9_to_18\n" \
  + "L\t18\t-\t9\t-\t4M\tID:Z:18_to_9\n" + "L\t0\t-\t12\t+\t5M\tID:Z:0_to_12\n" \
  + "L\t0\t+\t13\t+\t6M\tID:Z:0_to_13\n" + "L\t7\t+\t12\t-\t3M\tID:Z:7_to_12\n" \
  + "L\t13\t+\t7\t-\t4M\tID:Z:13_to_7\n" + "P\t14\t11+,12+\t122M\n" \
  + "P\t15\t11+,13+\t120M\n"

#                                                             ___________
#                                                            |           |
#   ___________      [14_14_14]                             [5_5_5]     [8_8_8]
#  |           |      |                                     /
# [10_10_10]  [11_11_11]                                   /
#                     |                              [1_1_1] --- [2_2_2] --- [6_6_6]
#                    [15_15_15]                            \
#    ____________                                           \              _______________
#   |            |                 ______                    \            |               |
#  [0_0_0]      [12_12_12]        |      |                     [3_3_3]   [4_4_4]   [23_23_23]
#       |               |         | [9_9_9]                         |_________|
#      [13_13_13]  [7_7_7]        |      |
#              |________|        [18_18_18]
#

class TestLine (unittest.TestCase):

  graph = pygfa.gfa.GFA()
  graph.from_string(gfa_file)
  
  def test_no_external_fasta(self):
    edges_no_consistency = []
    edges_no_calculate = ['1_to_2', '1_to_3', '1_to_5', '5_to_8', \
      '11_to_14', '9_to_18', '18_to_9', '0_to_12', '0_to_13', '13_to_7']
    no_fasta_no_consistency, no_fasta_no_defined = self.graph.overlap_consistency()
    self.assertTrue(no_fasta_no_consistency == edges_no_consistency)
    for edge in edges_no_calculate:
      self.assertTrue(edge in no_fasta_no_defined)

  def test_consistency_true(self):
    edges_no_consistency = []
    edges_no_calculate = []
    correct_no_consistency, correct_no_defined = self.graph.overlap_consistency('data/check_overlap_test_correct.fasta')
    self.assertTrue(correct_no_consistency == edges_no_consistency)
    self.assertTrue(correct_no_defined == edges_no_calculate)
  
  def test_consistency_false(self):
    edges_no_consistency = ['1_to_2', '1_to_3', '1_to_5', '11_to_14', '0_to_13']
    edges_no_calculate = ['5_to_8']
    fail_no_consistency, fail_no_defined = self.graph.overlap_consistency('data/check_overlap_test_fail.fasta')
    for edge in edges_no_consistency:
      self.assertTrue(edge in fail_no_consistency)  
    for edge in edges_no_calculate:
      self.assertTrue(edge in fail_no_defined)

  def test_wrong_fasta_file(self):
    file_error = self.graph.overlap_consistency('data/check_overlap_test.fasta')
    self.assertTrue(file_error == None)

if  __name__ == '__main__':
    unittest.main()
