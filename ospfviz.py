#!/usr/bin/env python
#
# OSPFViz
# (C) 2013 CZ.NIC, z.s.p.o.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import pickle
import pygraphviz as pgv
import socket
import getopt

ipcache = {}

def resolve_ip(ip,db=None,dns=True):
    if db:
        if ip in db:
            return db[ip]

    if ip in ipcache:
        return ipcache[ip]

    if dns:
        try:
            name = socket.gethostbyaddr(ip)[0]
            ipcache[ip] = name
            return name
        except:
            ipcache[ip] = ip
            return ip

    return ip

def parse_input(lines):
    def line_rank(line):
        r = 0
        for c in l:
            if c == '\t':
                r+=1
            else:
                return r
            
    routers = []
    router_network = {}
    router_external = {}
    network_address = {}

    cur_area = '0.0.0.0'
    cur_type = None
    cur_key = None
    for l in lines:
        ls = str.split(l)
        if(len(ls) <= 1):
            continue
        lr = line_rank(l)

        if lr == 0:
            cur_area = ls[1]
        if lr == 1:
            if ls[0] == 'router':
                cur_type = 'router'
                cur_key = ls[1]
                routers.append(cur_key)
            elif ls[0] == 'network':
                cur_type = 'network'
                cur_key = ls[1]
            else:
                raise Exception("Unknown type: "+ls[0]+" on line "+l)
        if lr == 2:
            if cur_type == 'network':
                if ls[0] == 'address':
                    network_address[cur_key] = ls[1]

            if cur_type == 'router':
                if ls[0] == 'network':
                    if not cur_key in router_network:
                        router_network[cur_key] = []
                    router_network[cur_key].append(ls[1])

                if ls[0] == 'external':
                    if not cur_key in router_external:
                        router_external[cur_key] = []
                    router_external[cur_key].append(ls[1])

    def transform_net_name(net,net_addr_table):
        if net in net_addr_table:
            return net_addr_table[net]
        else:
            return net

    for rnk in router_network.keys():
        router_network[rnk] = [transform_net_name(rne,network_address) for rne in router_network[rnk]]

    return (routers,router_network,router_external)



FONT_SIZE = 8
LABEL_FONT_SIZE = 10
LINE_WIDTH = 0.5

ROUTER_SHAPE='box'
NETWORK_SHAPE='ellipse'
EXTERNAL_SHAPE='diamond'

COLOR_OK='green'
COLOR_MISSING='red'
COLOR_UNKNOWN='grey'

def graph_gen(current_graph, diff_graph,filename=None,draw_external=False):
    (routers,router_networks,router_externals) = current_graph
    (routers_missing,router_networks_missing,router_externals_missing) = diff_graph

    def transform_nodename(name):
        return name.replace(":", "")

    def transform_label(s):
        return "".join(["&#%d;"%ord(x) for x in s])

    def add_node(graph,v,node_type='router',fillcolor=None):
        vid = transform_nodename(v)
        if(not graph.has_node(vid)):
            params = {}
            if(node_type == 'router'):
                params = {'fontsize':FONT_SIZE,'shape':ROUTER_SHAPE,'style':'rounded','label':transform_label(resolve_ip(v))}
            elif(node_type == 'network'):
                params = {'fontsize':FONT_SIZE,'shape':NETWORK_SHAPE,'label':transform_label(v)}
            elif(node_type == 'external'):
                params = {'fontsize':FONT_SIZE,'shape':EXTERNAL_SHAPE,'label':transform_label(v)}

            if(fillcolor):
                if 'style' in params:
                    params['style'] = params['style']+',filled'
                else:
                    params['style']='filled'
                params['fillcolor']=fillcolor
            graph.add_node(vid,**params)

    def add_edge(graph,v1,v2,color='black',style='solid',penwidth=LINE_WIDTH,label=None):
        if(v1==v2):
            return

        vid1 = transform_nodename(v1)
        vid2 = transform_nodename(v2)

        if(not graph.has_edge((vid1,vid2))):
            params = {'color':color,'style':style,'penwidth':penwidth}
            if label:
                params['fontsize']=LABEL_FONT_SIZE
                params['label']=transform_label(" "+label+"  ")
            graph.add_edge((vid1,vid2),**params)



    gr = pgv.AGraph(overlap='scalexy',splines='true')

    for r in routers:
        add_node(gr,r,node_type='router',fillcolor=COLOR_OK)

    for rnk in router_networks.keys():
        for rn in router_networks[rnk]:
            add_node(gr,rn,node_type='network',fillcolor=COLOR_OK)
            add_edge(gr,rnk,rn,color=COLOR_OK)

    if draw_external:
        for rek in router_externals.keys():
            for re in router_externals[rek]:
                add_node(gr,re,node_type='external',fillcolor=COLOR_OK)
                add_edge(gr,rek,re,color=COLOR_OK)

    for r in routers_missing:
        add_node(gr,r,node_type='router',fillcolor=COLOR_MISSING)

    for rnk in router_networks_missing.keys():
        for rn in router_networks_missing[rnk]:
            add_node(gr,rn,node_type='network',fillcolor=COLOR_MISSING)
            add_edge(gr,rnk,rn,color=COLOR_MISSING)

    if draw_external:
        for rek in router_externals_missing.keys():
            for re in router_externals_missing[rek]:
                add_node(gr,re,node_type='external',fillcolor=COLOR_MISSING)
                add_edge(gr,rek,re,color=COLOR_MISSING)



    gr.layout(prog='neato')
    if filename:
        gr.draw(filename,format='svg')
    else:
        print gr.draw(format='svg')


def load_data(filename):
    try:
        return pickle.load(open(filename, 'rb'))
    except:
        return [[],{},{}]

def save_data(graph,filename):
    pickle.dump(graph,open(filename, 'wb'))

def merge_graph(curr,last):
    def merge_dict(c,l):
        result = {}
        for ck in c.keys():
            if ck in l:
                result[ck] = list(set(c[ck] + l[ck]))
            else:
                result[ck] = c[ck]

        for lk in l.keys():
            if lk in result:
                result[lk] = list(set(l[lk] + result[lk]))
            else:
                result[lk] = l[lk]
        return result

    return (list(set(curr[0]+last[0])), merge_dict(curr[1],last[1]), merge_dict(curr[2],last[2]))

def diff_graph(curr,last):
    def diff_dict(c,l):
        r = {}
        for lk in l.keys():
            if lk in c:
                r[lk] = list(set(l[lk]).difference(c[lk]))
            else:
                r[lk] = l[lk]
        return r

    return [list(set(last[0]).difference(curr[1])),diff_dict(curr[1],last[1]),diff_dict(curr[2],last[2])]
            

def print_help():
    print """ospfviz.py --  OSPF vizualization script
Options:
  -h,--help : print help
  -o,--output : output PNG file
  -i,--input : input text file (unspecified = stdin)
  -e,--external : draw external routes
  -s,--save : save file to keep state
"""

def main():
    try:
        options,remainder = getopt.getopt(sys.argv[1:], 'o:i:es:h',
                                          ['output=',
                                           'input=',
                                           'external',
                                           'save=',
                                           'help'
                                           ])
    except:
        print_help()
        sys.exit(-1)

    outfile = None
    infile = None
    savefile = 'ospfviz.save'
    external = False

    for o in options:
        if o[0] == '-o' or o[0] == '--output':
            outfile = o[1]
        elif o[0] == '-i' or o[0] == '--input':
            infile = o[1]
        elif o[0] == '-s' or o[0] == '--save':
            savefile = o[1]
        elif o[0] == '-e' or o[0] == '--external':
            external = True
        elif o[0] == '-h' or o[0] == '--help':
            print_help()
            sys.exit(0)

    lines = []
    if infile:
        lines = open(infile,'r').readlines()
    else:
        lines = sys.stdin.readlines()

    curr = parse_input(lines)
    last = load_data(savefile)
    diff = diff_graph(curr,last)
    merged = merge_graph(curr,last)
    save_data(merged,savefile)
    graph_gen(curr,diff,outfile,draw_external=external)




if __name__=="__main__":
    main()
