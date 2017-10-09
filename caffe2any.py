#!/usr/bin/python

"""

"""
import sys
import argparse
from collections import deque, Counter
import caffe_pb2 as caffe
from google.protobuf import text_format
from printers.png import PngPrinter
from printers import csv, console
from caffe_parser import parse_caffe_net
from transforms import reduce_transforms
import topology
import yaml
import logging


def sum_blob_mem(tplgy, node, blobs, sum):
    if node.type == "Input" or node.role == "Modifier":
        return
    out_edges = tplgy.find_outgoing_edges(node)
    for out_edge in out_edges:
        if out_edge.blob not in blobs:
            shape = out_edge.blob.shape
            sum[0] += out_edge.blob.size()
            blobs.append(out_edge.blob)


from transforms.update_blobs_sizes import update_blobs_sizes, __update_blobs_sizes
from transforms import fold_transforms
from transforms import decorator_transforms


def apply_transforms(prefs, tplgy):
    ''' Handle optional transform processing on the topology
    '''
    if prefs['remove_dropout']:
        tplgy.remove_node_by_type('Dropout')
    if prefs['fold_batchnorm']:
        fold_transforms.fold_pair(tplgy, 'Convolution', 'BatchNorm')
    if prefs['fold_scale']:
        fold_transforms.fold_pair(tplgy, 'Convolution', 'Scale')
    if prefs['merge_conv_relu']:
        tplgy.merge_nodes('Convolution', 'ReLU')
        # tplgy.merge_nodes('Convolution', 'PReLU')
    if prefs['merge_conv_relu_pooling']:
        tplgy.merge_nodes('Convolution_ReLU', 'Pooling')
        # tplgy.merge_nodes('Convolution_PReLU', 'Pooling')
    if prefs['merge_ip_relu']:
        tplgy.merge_nodes('InnerProduct', 'ReLU')
    if prefs['merge_sum_relu']:
        tplgy.merge_nodes('Eltwise', 'ReLU')
        # tplgy.merge_nodes('Eltwise', 'PReLU')
    #decorator_transforms.horizontal_fusion(tplgy)

import logging.config
#logging.config.fileConfig('logging.conf')


def main():
    print("caffe2any v0.5")
    # logger = logging.getLogger('topology')

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--printer', help='output printer (csv, console, png)', default='console')
    parser.add_argument('-d', '--display', type=str, help='display inventory,unique,output,bfs,mem')
    parser.add_argument('infile', help='input prototxt file')
    args = parser.parse_args()

    net = caffe.NetParameter()

    # Read a Caffe prototxt file
    try:
        f = open(sys.argv[1], "rb")
        text_format.Parse(f.read(), net)
        f.close()
    except IOError:
        exit("Could not open file " + sys.argv[1])

    tplgy = parse_caffe_net(net)
    # calculate BLOBs sizes
    #tplgy.traverse(lambda node: update_blobs_sizes(tplgy, node)) # weird recursion, why oh why?!
    tplgy.traverse(lambda node: __update_blobs_sizes(tplgy, node))

    # read preferences
    with open("caffe2any_cfg.yml", 'r') as cfg_file:
        prefs = yaml.load(cfg_file)

    apply_transforms(prefs['transforms'], tplgy)

    # tplgy.dump_edges()
    if args.printer == 'console':
        printer = console.ConsolePrinter()
    elif args.printer == 'png':
        printer = PngPrinter(args, prefs['png'], net)
    else:
        printer = csv.CsvPrinter(args.infile + '.csv')

    if args.display != None:
        for disp_opt in args.display.split(','):
            if disp_opt == 'inventory':
                printer.print_inventory( reduce_transforms.get_inventory(tplgy) )
            elif disp_opt == 'unique':
                printer.print_unique_all( reduce_transforms.get_uniques_inventory(tplgy) )
            elif disp_opt == 'output':
                print("outputs:")
                outputs = tplgy.find_output_blobs()
                for output in outputs:
                    print('\t' + output)
            elif disp_opt == 'bfs':
                printer.print_bfs(tplgy)
            elif disp_opt == 'mem':
                sum = [0]
                blobs = []
                tplgy.traverse(lambda node: sum_blob_mem(tplgy, node, blobs, sum))
                print("Total BLOB memory: " + str(sum[0]))
            else:
                exit ("Error: invalid display option")


if __name__ == '__main__':
    main()
