


def reverse_and_complement(string):
	reverse_dict= dict([('A', 'T'), ('T', 'A'), ('C', 'G'), ('G', 'C'), ('*', '*')])
	complement_string = ''.join([reverse_dict[c] for c in string])
	return complement_string[::-1]

def reverse_strand(strand):
	dict_inverted = dict([('+', '-'), ('-', '+'), (None, None)])
	return dict_inverted[strand]

def update_dictionary(from_list, to_list, i, orn):
	
	keep_id, keep_orn = from_list[i]
	remove_id, remove_orn = to_list[i]

	i = 0
	while i < len(from_list):
		if from_list[i] == (keep_id, keep_orn):
			from_list.pop(i)
			to_list.pop(i)
		else:
			if from_list[i][0] == remove_id:
				if orn == '-+' or orn == '+-':
					from_list[i] = (keep_id, reverse_strand(from_list[i][1]))
					if not from_list[i][1]:
						to_list[i] = (to_list[i][0], reverse_strand(to_list[i][1]))
				else:
					from_list[i] = (keep_id, from_list[i][1])
			if to_list[i][0] == remove_id:
				if orn == '-+' or orn == '+-':
					to_list[i] = (keep_id, reverse_strand(to_list[i][1]))
				else:
					to_list[i] = (keep_id, to_list[i][1])
			i += 1

def update_graph(gfa_, keep_node, remove_node, new_seq, overlap, orn):

	keep_id, keep_orn = keep_node
	remove_id, remove_orn = remove_node

	gfa_.node()[keep_id]['sequence'] = new_seq
	if not new_seq == '*':
		gfa_.node()[keep_id]['slen'] = len(gfa_.node(keep_id)['sequence'])
	else:
		if gfa_.node()[keep_id]['slen'] and gfa_.node()[remove_id]['slen']:
			gfa_.node()[keep_id]['slen'] += gfa_.node()[remove_id]['slen'] - overlap
		else:
			gfa_.node()[keep_id]['slen'] = None
		
		if 'fu' in gfa_.node()[remove_id]:
			remove_fu = gfa_.node()[remove_id].get('fu').lstrip('Z:')
		else:
			remove_fu = remove_id

		if 'fu' in gfa_.node()[keep_id]:
			gfa_.node()[keep_id]['fu'] += '_'+remove_fu
		else:
			gfa_.node()[keep_id]['fu'] = 'Z:'+keep_id+'_'+remove_fu

	#fix gfa_.node()[keep_id]['option']

	remove_edge_list = []
	data_update_edges = gfa_.edge()[remove_id]
	for node in data_update_edges:
		for edge_id in data_update_edges[node]:
			if data_update_edges[node][edge_id]['from_node'] == remove_id:
				parse_from_node = keep_id
				parse_from_orn = data_update_edges[node][edge_id]['from_orn']
				if not parse_from_orn:
					parse_to_node = data_update_edges[node][edge_id]['to_node']
					parse_to_orn = data_update_edges[node][edge_id]['to_orn']
					parse_from_positions = data_update_edges[node][edge_id]['from_positions']
					parse_to_positions = data_update_edges[node][edge_id]['to_positions']
					keep_slen = int(gfa_.node()[keep_id]['slen'])
					remove_slen = int(gfa_.node()[remove_id]['slen'])
					if orn == '-+':
						parse_to_orn = reverse_strand(parse_to_orn)
						parse_from_positions = (str(remove_slen-int(parse_from_positions[1])),\
							str(remove_slen-int(parse_from_positions[0])))
					elif orn == '+-':
						parse_to_orn = reverse_strand(parse_to_orn)
						parse_from_positions = (str(keep_slen-int(parse_from_positions[1])),\
							str(keep_slen-int(parse_from_positions[0])))
					elif orn == '++':
						parse_from_positions = (str(keep_slen-remove_slen+int(parse_from_positions[0])),\
							str(keep_slen-remove_slen+int(parse_from_positions[1])))
				else:
					if orn == '-+' or orn == '+-':
						parse_from_orn = reverse_strand(parse_from_orn)
					parse_to_node = data_update_edges[node][edge_id]['to_node']
					parse_to_orn = data_update_edges[node][edge_id]['to_orn']
			else:
				parse_to_node = keep_id
				parse_to_orn = data_update_edges[node][edge_id]['to_orn']
				if orn == '-+' or orn == '+-':
					parse_to_orn = reverse_strand(parse_to_orn)
				parse_from_node = data_update_edges[node][edge_id]['from_node']
				parse_from_orn = data_update_edges[node][edge_id]['from_orn']
			parse_overlap = data_update_edges[node][edge_id]['alignment']
			
			if parse_from_orn:
				parse_new_edge = 'L\t'+parse_from_node+'\t'+parse_from_orn+'\t'\
					+parse_to_node+'\t'+parse_to_orn+'\t'+parse_overlap
			else:
				parse_new_edge = 'F\t'+parse_from_node+'\t'+parse_to_node+parse_to_orn+'\t'\
					+parse_from_positions[0]+'\t'+parse_from_positions[1]+'\t'\
					+parse_to_positions[0]+'\t'+parse_to_positions[1]+'\t'+parse_overlap[0]

			gfa_.add_edge(parse_new_edge)
			remove_edge_list.append(edge_id)

	for remove_edge_id in remove_edge_list:
		gfa_.remove_edge(remove_edge_id)
	gfa_.remove_node(remove_id)

def compact_sequence(gfa_, from_node, to_node):
	from_id, from_orn = from_node
	to_id, to_orn = to_node

	edges = gfa_._search_edge_by_nodes((from_id, to_id))
	for edge in edges:
		overlap = int(edges[edge]['alignment'].rstrip('M'))
	gfa_.remove_edge(edge)

	from_seq = gfa_.node(from_id)['sequence']
	to_seq = gfa_.node(to_id)['sequence']
	
	#print(from_id+' '+from_orn+' '+from_seq+'\t\t\t'+to_id+' '+to_orn+' '+to_seq)

	if from_orn == '-' and to_orn == '-':
		if from_seq == '*' or to_seq =='*':
			new_seq = '*'
		else:
			new_seq = to_seq+from_seq[overlap:]
		return new_seq, overlap, '--'
	elif from_orn == '+' and to_orn == '+':
		if from_seq == '*' or to_seq =='*':
			new_seq = '*'
		else:	
			new_seq = from_seq+to_seq[overlap:]
		return new_seq, overlap, '++'
	elif from_orn == '-':
		if from_seq == '*' or to_seq =='*':
			new_seq = '*'
		else:
			new_seq = reverse_and_complement(to_seq)[:-overlap]+from_seq
		return new_seq, overlap, '-+'
	else:
		if from_seq == '*' or to_seq =='*':
			new_seq = '*'
		else:
			new_seq = from_seq+reverse_and_complement(to_seq)[overlap:]
		return new_seq, overlap, '+-'

def compression_graph(gfa_):

	from_list = []
	to_list = []
	eid_list = []

	data_edges = gfa_.edge()
	for node1 in data_edges:
		for node2 in data_edges[node1]:
			for eid in data_edges[node1][node2]:
				if eid_list.count(eid) == 0:
					eid_list.append(eid)
					from_list.append((data_edges[node1][node2][eid]['from_node'],\
						data_edges[node1][node2][eid]['from_orn']))
					to_list.append((data_edges[node1][node2][eid]['to_node'],\
						data_edges[node1][node2][eid]['to_orn']))

	#for i in range(len(from_list)):
	#	print(str(i)+' '+str(from_list[i])+' '+str(to_list[i]))
	
	count_edge_compacted = 0
	i = len(from_list) - 1
	while i >= 0:
		if from_list[i][1] and from_list.count(from_list[i]) == 1 and \
			to_list.count(to_list[i]) == 1:
			inverted_from = (from_list[i][0], reverse_strand(from_list[i][1]))
			inverted_to = (to_list[i][0], reverse_strand(to_list[i][1]))
			if to_list.count(inverted_from) == 0 and \
				from_list.count(inverted_to) == 0:
				new_seq, overlap, orn = compact_sequence(gfa_, from_list[i], to_list[i])
				update_graph(gfa_, from_list[i], to_list[i], new_seq, overlap, orn)
				update_dictionary(from_list, to_list, i, orn)
				count_edge_compacted += 1
		i -= 1


	#for i in range(len(from_list)):
	#	print(str(i)+' '+str(from_list[i])+' '+str(to_list[i]))
		
	print(str(count_edge_compacted)+' edges has been compacted')