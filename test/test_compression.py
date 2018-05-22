import sys
sys.path.insert(0, '../')

import copy
import unittest

import pygfa

gfa_file = "H\tac:Z:test2\n" + "H\tVN:Z:1.0\n" + "H\taa:i:12\tab:Z:test1\n" \
  + "H\taa:i:15\n" + "S\t1\t*\n" + "S\t2\tAAAAAGGCG\n" + "S\t3\tAAAAATCT\n" \
  + "S\t4\tGGGTTTTTAGA\n" + "S\t5\t*\n" + "S\t6\tGGCGAAAAA\n" + "S\t8\t*\n" \
  + "S\t23\tTTTTTGGG\n" + "S\t10\t*\n" + "S\t11\tGTCGAAAAA\n" + "S\t14\t*\n" \
  + "S\t15\t*\n" + "S\t9\t*\n" + "S\t18\t*\n" + "S\t0\tGGCCGAAAAACCTCGC\n" \
  + "S\t7\t*\n" + "S\t12\tCGGCCAAAAA\n" + "S\t13\t*\tLN:i:100\n" \
  +"L\t1\t+\t2\t+\t12M\tID:Z:1_to_2\n" + "L\t1\t+\t3\t+\t12M\tID:Z:1_to_3\n" \
  + "C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\n" + "C\t2\t+\t6\t+\t10\t4M\tID:Z:2_to_6\n" \
  + "L\t3\t+\t4\t-\t3M\tID:Z:3_to_4\n" + "L\t4\t-\t23\t-\t3M\tID:Z:4_to_23\n" \
  + "L\t5\t-\t8\t+\t122M\tID:Z:5_to_8\n" + "L\t10\t-\t11\t+\t4M\tID:Z:10_to_11\n" \
  + "L\t11\t+\t14\t+\t122M\tID:Z:11_to_14\n" + "L\t11\t+\t15\t+\t120M\tID:Z:11_to_15\n" \
  + "L\t9\t+\t18\t-\t25M\tID:Z:9_to_18\n" + "L\t18\t-\t9\t-\t10M\tID:Z:18_to_9\n" \
  + "L\t0\t-\t12\t+\t5M\tID:Z:0_to_12\n" + "L\t0\t+\t13\t+\t6M\tID:Z:0_to_13\n" \
  + "L\t7\t+\t12\t-\t3M\tID:Z:7_to_12\n" + "L\t13\t+\t7\t-\t11M\tID:Z:13_to_7\n" \
  + "P\t14\t11+,12+\t122M\n" + "P\t15\t11+,13+\t120M\n"

# Before Compression
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

# After Compression
#                                    ______
#                                   |      |                  ___________
#                                   | [9_9_9]                |           |
#                    [14_14_14]     |      |                [5_5_5]     [8_8_8]
#                     |            [18_18_18]               /
# [10'_10'_10'_11_11_11]                                   /
#                     |                              [1_1_1] --- [2_2_2_6_6_6]
#                    [15_15_15]                            \
#    ____________________________________                   \
#   |                                    |                   \
#  [12'_12'_12'_0_0_0_13_13_13]     [7_7_7]                  [3_3_3_4'_4'_4'_23'_23'_23']
#                            |___________|
#

class TestLine (unittest.TestCase):

  graph = pygfa.gfa.GFA()
  graph.from_string(gfa_file)
  
  def test_compression(self):
    
    before_node = ['10', '11', '14', '15', '9', '18', '0', '12', '13', '7',\
      '1', '5', '8', '2', '6', '3', '4', '23']
    before_edge = [('10', '11'), ('11', '14'), ('11', '15'), \
      ('9', '18'), ('18', '9'), \
      ('0', '12'), ('0', '13'), ('13', '7'), ('7', '12'), \
      ('1', '2'), ('1', '3'), ('1', '5'), ('2', '6'), ('3', '4'), ('4', '23'), ('5', '8')]
    before_len = [1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    
    for node in before_node:
      self.assertTrue(node in list(self.graph.node()))
    i = 0
    for edge in before_edge:
      self.assertTrue(len(self.graph._search_edge_by_nodes(edge)) == before_len[i])
      i += 1

    self.graph.compression()

    after_node = ['10', '14', '15', '9', '18', '0', '7', '1', '5', '8', '2', '3']
    removed_node = ['11', '6', '12', '13', '4', '23']

    after_edge = [('10', '14'), ('10', '15'), \
      ('9', '18'), ('18', '9'), \
      ('0', '7'), ('7', '0'), \
      ('1', '2'), ('1', '3'), ('1', '5'), ('5', '8')]
    after_len = [1, 1, 2, 2, 2, 2, 1, 1, 1, 1]
    removed_edge = [('10', '11'), ('0', '12'), ('0', '13'), ('2', '6'), ('3', '4'), ('4', '23')]

    for node in after_node:
      self.assertTrue(node in list(self.graph.node()))
    for node in removed_node:
      self.assertTrue(not(node in list(self.graph.node())))
    i = 0
    for edge in after_edge:
      self.assertTrue(len(self.graph._search_edge_by_nodes(edge)) == after_len[i])
      i += 1
    for edge in removed_edge:
      self.assertTrue(not self.graph._search_edge_by_nodes(edge))   

if  __name__ == '__main__':
    unittest.main()
