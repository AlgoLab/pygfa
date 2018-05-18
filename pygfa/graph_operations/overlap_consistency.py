from pygfa.graph_operations.compression import reverse_and_complement
import sys
import difflib

def fasta_reader(path, fasta_file):
	"""Given the path and external fasta file
	read the fasta and create a dictionary used to
	map id(key) and sequence(value) from the file.
	:return dictionary with mapping: if esternal file is valid
	:return None: otherwise
	"""
	fasta_dict = dict()
	try:
		with open(path + fasta_file) as external_file:
			fasta_rows = external_file.readlines()
			i = 0
			for i in range(len(fasta_rows)):
				if fasta_rows[i][0] == '>':
					id_fasta = fasta_rows[i].lstrip('>').rstrip('\n')
					sequence_rows = []
					i += 1
					while not fasta_rows[i][0] == '>':
						sequence_rows.append(fasta_rows[i].rstrip('\n'))
						i += 1
						if i >= len(fasta_rows):
							break
					sequence = ''.join([row for row in sequence_rows])
					fasta_dict[id_fasta] = sequence
			external_file.close()
	except:
		print('External fasta file not exist!')
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
		print('Edge between node '+from_id+' and '+to_id+ \
			' have no consistency between CIGAR overlap end "real" overlap')
		return False

	return True

def check_overlap(gfa_, path, external_file):
	"""The function look all the edge and take information
	of the involved node. If there is an external fasta file
	create a dictionary for mapping the id and sequence to use.
	Using different other function calcolate the sequence
	overlap and make a control with the CIGAR overlap, and
	determinate the nuber of edge that are consistent.
	"""

	if external_file:
		fasta_dict = fasta_reader(path, external_file)
		if not fasta_dict:
			return None

	eid_list = []
	node_dict = dict()
	count_consistency = 0

	data_edges = gfa_.edge()
	for node1 in data_edges:
		for node2 in data_edges[node1]:
			for eid in data_edges[node1][node2]:
				if eid_list.count(eid) == 0:
					eid_list.append(eid)
					from_id = data_edges[node1][node2][eid]['from_node']
					node_dict[from_id] = gfa_.node()[from_id]['sequence']
					to_id = data_edges[node1][node2][eid]['to_node']
					node_dict[to_id] = gfa_.node()[to_id]['sequence']
					
					from_orn = data_edges[node1][node2][eid]['from_orn']
					to_orn = data_edges[node1][node2][eid]['to_orn']
					overlap = int(data_edges[node1][node2][eid]['alignment'].rstrip('M'))				

					if node_dict[from_id] == '*' and external_file:
						node_dict[from_id] = fasta_dict.get(from_id, '*')
					if node_dict[from_id] == '*':
						print('Node '+ from_id +' has sequence no specify!')
					if node_dict[to_id] == '*' and external_file:
						node_dict[to_id] = fasta_dict.get(to_id, '*')
					if node_dict[to_id] == '*':
						print('Node '+ to_id +' has sequence no specify!')

					if not node_dict[from_id] == '*' and not node_dict[to_id] == '*':
						check = consistency((from_id, to_id), (node_dict[from_id], node_dict[to_id]), (from_orn, to_orn), overlap)
						if check == True:
							count_consistency += 1
					else:
						print('Can\'t check overlap consistency between node '+ from_id+ ' and '+ to_id)

	print(str(count_consistency)+' edge overlap are consistency of total amount of '+str(len(eid_list)))