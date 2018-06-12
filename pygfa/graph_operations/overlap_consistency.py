from pygfa.graph_operations.compression import reverse_and_complement
import sys
import difflib
import logging
from Bio import SeqIO

GRAPH_LOGGER = logging.getLogger(__name__)

def fasta_reader(path, fasta_file):
	"""Given the path and external fasta file
	read the fasta and create a dictionary used to
	map id(key) and sequence(value) from the file.
	:return dictionary with mapping: if esternal file is valid
	:return None: otherwise
	"""
	fasta_dict = dict()
	try:
		for seq_record in SeqIO.parse(path + fasta_file, "fasta"):
			id_fasta = seq_record.id
			sequence = seq_record.seq
			fasta_dict[id_fasta] = sequence
	except:
		GRAPH_LOGGER.debug('External fasta file not exist!')
		return None

	return fasta_dict

def real_overlap(from_sequence, to_sequence):
	"""Given in input 2 sequence
	find the overlap, final part of from_sequence and
	start part of to_sequence that have match.
	:return the overlap lenght
	"""
	sequence_overlap = difflib.SequenceMatcher(None, from_sequence, to_sequence)
	i= 0
	start = 0
	start_pos_from = -1
	start_pos_to = -1
	size = -1
	while not start_pos_to == 0 or not start_pos_from+size == len(from_sequence):
		i += 1
		if i > 10:
			break
		start_pos_from, start_pos_to, size = sequence_overlap.find_longest_match(start, len(from_sequence), \
			0, len(to_sequence))
		if not start_pos_to == 0 or not start_pos_from+size == len(from_sequence):
			start = start_pos_from+1

	return size

def consistency(node, sequence, orientation, overlap):
	"""Given node information and overlap
	compare the CIGAR overlap and the sequence overlap.
	:return True: if CIGAR overlap and sequence overlap are consistency
	:return False: otherwise
	"""
	from_id, to_id = node
	from_sequence, to_sequence = sequence
	from_orn, to_orn = orientation	
	if from_orn == '-':
		from_sequence = reverse_and_complement(from_sequence)
	if to_orn == '-':
		to_sequence = reverse_and_complement(to_sequence)
	size_overlap = real_overlap(from_sequence, to_sequence)
	if not size_overlap == overlap:
		GRAPH_LOGGER.debug('Edge between node '+from_id+' and '+to_id+ \
			' have no consistency between CIGAR overlap end "real" overlap')
		GRAPH_LOGGER.debug('real\t'+ str(size_overlap))
		GRAPH_LOGGER.debug('cigar\t'+ str(overlap))
		return False

	return True

def check_overlap(gfa_, path, external_file):
	"""The function look all the edge and take information
	of the involved node. If there is an external fasta file
	create a dictionary for mapping the id and sequence to use.
	Using different other function calcolate the sequence
	overlap and make a control with the CIGAR overlap, and
	determinate the nuber of edge that are consistent.
	:return edges_no_consistency, edges_no_calculate: if external fasta file is defined or not specify
	:return None: if external file has a wrong name
	"""
	if external_file:
		fasta_dict = fasta_reader(path, external_file)
		if not fasta_dict:
			return None

	eid_dict = dict()
	node_dict = dict()

	count_consistency = 0
	count_no_defined = 0
	edges_no_consistency = []
	edges_no_calculate = []
	edge_text = 0

	data_edges = gfa_.edge()
	for node1 in data_edges:
		for node2 in data_edges[node1]:
			for eid in data_edges[node1][node2]:
				if not eid_dict.get(eid):
					eid_dict[eid] = True
					from_id = data_edges[node1][node2][eid]['from_node']
					try:
						node_dict[from_id] = gfa_.node()[from_id]['sequence']
					except:
						edge_text += 1
						break
					to_id = data_edges[node1][node2][eid]['to_node']
					try:
						node_dict[to_id] = gfa_.node()[to_id]['sequence']
					except:
						edge_text += 1
						break
					
					from_orn = data_edges[node1][node2][eid]['from_orn']
					to_orn = data_edges[node1][node2][eid]['to_orn']
					overlap = int(data_edges[node1][node2][eid]['alignment'].rstrip('M'))				

					if node_dict[from_id] == '*' and external_file:
						node_dict[from_id] = fasta_dict.get(from_id, '*')
					if node_dict[from_id] == '*':
						GRAPH_LOGGER.debug('Node '+ from_id +' has sequence no specify!')
					if node_dict[to_id] == '*' and external_file:
						node_dict[to_id] = fasta_dict.get(to_id, '*')
					if node_dict[to_id] == '*':
						GRAPH_LOGGER.debug('Node '+ to_id +' has sequence no specify!')

					if not node_dict[from_id] == '*' and not node_dict[to_id] == '*':
						check = consistency((from_id, to_id), (node_dict[from_id], node_dict[to_id]), (from_orn, to_orn), overlap)
						if check == True:
							count_consistency += 1
						else:
							edges_no_consistency.append(eid)
					else:
						GRAPH_LOGGER.debug('Can\'t check overlap consistency between node ' \
							+ from_id+ ' and '+ to_id)
						count_no_defined += 1
						edges_no_calculate.append(eid)

	GRAPH_LOGGER.debug(str(count_consistency)+' edge overlap are consistency of total amount of '+str(len(eid_dict)-edge_text))

	return edges_no_consistency, edges_no_calculate