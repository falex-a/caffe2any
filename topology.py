"""
http://www.bogotobogo.com/python/python_graph_data_structures.php
A set of classes to model a DL topology

Todo: add find_input_blobs
Todo: remove Node.layer
"""
from collections import OrderedDict, deque
import math
import copy
import logging

tlogger = logging.getLogger(__name__)
fh = logging.FileHandler("output/log")
tlogger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
# add handler to logger object
tlogger.addHandler(fh)

#tlogger.debug("boo")


def log():
    return tlogger


class Node:
    def __init__(self, name, type, role):
        self.name = name
        self.type = type
        self.role = role
        self.attributes = {}

    def __str__(self):
        return self.name + '(' + self.type + ')'

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.name == other.name

    def is_same(this, other):
        return True

    def get_MACs(self):
            return 0

    def get_attr(self, name):
        try:
            return self.attributes[name]
        except KeyError:
            return None

    def set_attr(self, name, val):
        self.attributes[name] = val

class PoolingNode(Node):
    def __init__(self, name, type, layer):
        Node.__init__(self, name, type, 'Producer')
        param = layer.pooling_param
        self.kernel_size = param.kernel_size
        self.stride = param.stride
        self.pad = param.pad
        self.pool_type = param.pool

    def is_same(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (self.kernel_size, self.stride, self.pad, self.pool_type) == (
        other.kernel_size, other.stride, other.pad, other.pool_type)

    def transform_ifm(self, ifm_shape):
        ofm_shape = copy.deepcopy(ifm_shape)
        ifmh = ifm_shape[2]
        ifmw = ifm_shape[3]
        ofmw = math.ceil((ifmw - self.kernel_size + 2.0 * self.pad) / self.stride) + 1
        ofmh = math.ceil((ifmh - self.kernel_size + 2.0 * self.pad) / self.stride) + 1
        ofmh_noceil = (ifmh - self.kernel_size + 2.0 * self.pad) / self.stride + 1
        # The OFM is square, but I calculate the edges with different rounding strategies.
        # If the edges have diffe, 'Deconvolution'rent values, then we need to use the "ceiling"/"same" method
        self.ceiling = (ofmh_noceil != ofmh)
        ofm_shape[2] = int(ofmh)
        ofm_shape[3] = int(ofmw)
        log().debug(str(ifm_shape) + '--> ' + str(ofm_shape))
        return ofm_shape


class ConvolutionNode(Node):
    def __init__(self, name, type, layer):
        Node.__init__(self, name, type, 'Producer')
        param = layer.convolution_param
        self.kernel_size = param.kernel_size
        self.stride = param.stride
        self.pad = param.pad
        self.num_output = param.num_output
        self.dilation = param.dilation if param.dilation else 1
        self.kernel_h = param.kernel_h if param.kernel_h else param.kernel_size
        self.kernel_w = param.kernel_w if param.kernel_w else param.kernel_size

    def is_same(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (self.kernel_size, self.stride, self.pad) == (other.kernel_size, other.stride, other.pad)

    def transform_ifm(self, ifm_shape):
        ofm_shape = copy.deepcopy(ifm_shape)
        ofm_shape[1] = self.num_output
        ifmh = ifm_shape[2]
        ifmw = ifm_shape[3]
        ofmh = (ifmh - self.kernel_h + 2.0 * self.pad/self.dilation ) / self.stride + 1
        ofmw = (ifmw -  self.kernel_w + 2.0 * self.pad/self.dilation ) / self.stride + 1
        ofm_shape[2] = int(ofmh)
        ofm_shape[3] = int(ofmw)
        log().debug(str(ifm_shape) + '--> ' + str(ofm_shape))
        return ofm_shape

    def get_MACs(self, ofms_descriptor, num_ifms):
        # macs = #OFMs*OFM_X*OFM_Y*#IFMs*K_X*K_Y
        num_ofms = ofms_descriptor[1] if ofms_descriptor else 0
        ofm_x = ofms_descriptor[2] if ofms_descriptor else 0
        ofm_y = ofms_descriptor[3] if ofms_descriptor else 0
        MACs = num_ofms * ofm_x * ofm_y * num_ifms * self.kernel_w * self.kernel_h
        return MACs


class PairNode(Node):
    def __init__(self, node1, node2):
        self.node1 = node1
        self.node2 = node2
        name = node1.name + "  ++  " + node2.name
        type = node1.type + '_' + node2.type
        #type = new_type if new_type is not None else node1.type + '_' + node2.type
        Node.__init__(self, name, type, node1.role)

    def is_same(self, other):
        return self.node1.is_same(other.node1) and self.node2.is_same(other.node2)


class DeconvolutionNode(Node):
    def __init__(self, name, type, layer):
        Node.__init__(self, name, type, 'Producer')
        param = layer.convolution_param
        self.kernel_w = self.kernel_h = self.kernel_size = param.kernel_size
        self.stride = param.stride
        self.pad = param.pad
        self.num_output = param.num_output

    def is_same(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (self.kernel_size, self.stride, self.pad) == (other.kernel_size, other.stride, other.pad)

    def transform_ifm(self, ifm_shape):
        ofm_shape = copy.deepcopy(ifm_shape)
        ofm_shape[1] = self.num_output
        ifmh = ifm_shape[2]
        ifmw = ifm_shape[3]
        # s*(W-1) + k - 2*P
        ofmh = self.stride * (ifmh-1) + self.kernel_size - 2 * self.pad
        ofmw = self.stride * (ifmw - 1) + self.kernel_size - 2 * self.pad
        ofm_shape[2] = int(ofmh)
        ofm_shape[3] = int(ofmw)
        log().debug(str(ifm_shape) + '--> ' + str(ofm_shape))
        return ofm_shape

    def get_MACs(self, ifms_descriptor, num_ofms):
        # macs = #IFMs*IFM_X*IFM_Y*#OFMs*K_X*K_Y
        num_ifms = ifms_descriptor[1] if ifms_descriptor else 0
        ifm_x = ifms_descriptor[2] if ifms_descriptor else 0
        ifm_y = ifms_descriptor[3] if ifms_descriptor else 0
        MACs = num_ifms * ifm_x * ifm_y * num_ofms * self.kernel_w * self.kernel_h
        return MACs

class InnerProductNode(Node):
    def __init__(self, name, type, layer):
        Node.__init__(self, name, type, 'Producer')
        self.num_output = layer.inner_product_param.num_output

    def transform_ifm(self, ifm_shape):
        ofm_shape = copy.deepcopy(ifm_shape)
        ofm_shape[3] = self.num_output  # ifm_shape[1] * ifm_shape[2] * ifm_shape[3]
        ofm_shape[1] = ofm_shape[2] = 1
        log().debug(str(ifm_shape) + '--> ' + str(ofm_shape))
        return ofm_shape


class LRNNode(Node):
    def __init__(self, name, type, layer):
        Node.__init__(self, name, type, 'Producer')
        param = layer.lrn_param
        self.norm_region = layer.lrn_param.norm_region
        self.local_size = layer.lrn_param.local_size
        self.alpha = layer.lrn_param.alpha  # default = 1.
        self.beta = layer.lrn_param.beta  # default = 0.75

    def is_same(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (self.norm_region, self.alpha, self.beta, self.local_size) == (
        other.norm_region, other.alpha, other.beta, other.local_size)

class ReshapeNode(Node):
    def __init__(self, name, type, layer):
        Node.__init__(self, name, type, 'Modifier')
        param = layer.reshape_param
        self.reshape_param = param.shape

    def transform_ifm(self, ifm_shape):
        ofm_shape = copy.deepcopy(ifm_shape)
        # Calculate the IFM size; to be used to calculate the inferred dimension
        ifm_size = ifm_shape[0] * ifm_shape[1] * ifm_shape[2] * ifm_shape[3]
        infer = -1 # the index of the inferred dimension
        for i in xrange(4):
            if self.reshape_param.dim[i] > 0:
                # Positive numbers are used directly, setting the corresponding dimension
                # of the output blob. In addition, two special values are accepted for any
                # of the target dimension values:
                ofm_shape[i] = self.reshape_param.dim[i]
                ifm_size /= ofm_shape[i]
            elif self.reshape_param.dim[i] == 0:
                # 0 means 'copy the respective dimension of the bottom layer'. That is,
                # if the bottom has 2 as its 1st dimension, the top will have 2 as its
                # 1st dimension as well, given dim: 0 as the 1st target dimension.
                ofm_shape[i] = ifm_shape[i]
                ifm_size /= ofm_shape[i]
            elif self.reshape_param.dim[i] == -1:
                # -1 stands for 'infer this from the other dimensions'. This
                # dimension is calculated to keep the overall element count the same as in
                # the bottom layer. At most one -1 can be used in a reshape operation.
                infer = i
            if infer>0:
                ofm_shape[infer] = ifm_size
        return ofm_shape

class EltwiseNode(Node):
    def __init__(self, name, type, layer):
        Node.__init__(self, name, type, 'Producer')
        self.operation = layer.eltwise_param.operation

class ConcatNode(Node):
    def __init__(self, name, type, layer):
        Node.__init__(self, name, type, 'Modifier')

    #def transform_ifm(self, ifm_shape):
    #    ofm_shape = copy.deepcopy(ifm_shape)
    #    return ofm_shape

def node_factory(name, type, layer, role):
    if type == "Pooling":
        new_node = PoolingNode(name, type, layer)
    elif type == "Convolution":
        new_node = ConvolutionNode(name, type, layer)
    elif type == "InnerProduct":
        new_node = InnerProductNode(name, type, layer)
    elif type == "LRN":
        new_node = LRNNode(name, type, layer)
    elif type == "Deconvolution":
        new_node = DeconvolutionNode(name, type, layer)
    elif type == "Reshape":
        new_node = ReshapeNode(name, type, layer)
    elif type == "Eltwise":
        new_node = EltwiseNode(name, type, layer)
    elif type == "Concat":
        new_node = ConcatNode(name, type, layer)
    else:
        new_node = Node(name, type, role)
    return new_node


class BLOB:
    def __init__(self, name, shape, producer):
        self.name = name
        self.shape = shape
        self.producer = producer

    def __str__(self):
        if self.shape != None:
            return 'BLOB [' + self.name + ': shape=' + str(self.shape) + ']'
        else:
            return 'BLOB [' + self.name + ': shape=None]'

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.name == other.name

    def size(self):
        if self.shape is None:
            return 0
        # shape[0] is the batch dimension, so don't count it
        return self.shape[1] * self.shape[2] * self.shape[3]


class Edge:
    def __init__(self, src_node, dst_node, blob):
        self.src_node = src_node
        self.dst_node = dst_node
        self.blob = blob
        self.is_deleted = False

    def __str__(self):
        desc = ((self.src_node.name if self.src_node else 'None') + ' ==> ' +
                str(self.blob) + ' ==> ' +
                (self.dst_node.name if self.dst_node else 'None'))
        if self.is_deleted:
            desc += " IS DELETED!!"
        return desc

class Topology:
    def __init__(self):
        """
        Keep the the vertices ordered by insertion, so that we have
        a starting point
        """
        self.__nodes = OrderedDict()
        self.__blobs = {}
        self.__edges = []
        self.__first_node = None
        tlogger.debug("created Topology object")

    def dump_edges(self):
        print('Dumping edges')
        print('-----------------------------------------')
        for edge in self.__edges:
            print(str(edge))

    def add_node(self, name, type, layer, role):
        new_node = node_factory(name, type, layer, role)
        self.__nodes[name] = new_node
        if self.__first_node is None:
            self.__first_node = new_node
        log().debug('created Node:' + name)
        return new_node

    def add_nodes(self, nodes_to_add):
        for node in nodes_to_add:
            self.__nodes[node.name] = node
            if self.__first_node is None:
                self.__first_node = node
            log().debug('created Node:' + node.name)

    def del_nodes(self, nodes_to_del):
        for node in nodes_to_del:
            self.del_node(node)

    def del_node(self, node):
        # remove all edges which enter/exit this node
        incoming_edges = self.find_incoming_edges(node)
        outgoing_edges = self.find_outgoing_edges(node)
        for edge in incoming_edges:
            self.del_edge(edge)
        for edge in outgoing_edges:
            self.del_edge(edge)
        # Fix the first_node pointer
        if self.__first_node == node:
            self.__first_node = None
        # Finally, delete the node and change its name (for debug)
        del self.__nodes[node.name]
        node.name = node.name + "[DELETED]"

    def remove_nodes(self, nodes):
        [self.remove_node(node) for node in nodes]

    # The difference between del_node and remove_node?
    # remove_node will del_node and also reconnect the edge around
    # the node that was removed
    def remove_node(self, node):
        incoming_edges = self.find_incoming_edges(node)
        outgoing_edges = self.find_outgoing_edges(node)
        for incoming_edge in incoming_edges:
            src = incoming_edge.src_node
            for outgoing_edge in outgoing_edges:
                self.add_edge(src, outgoing_edge.dst_node, incoming_edge.blob)
        self.del_node(node)

    def remove_node_by_type(self, type_to_remove):
        done = False
        while not done:
            done = True
            for node_name in list(self.__nodes.keys()):
                node = self.__nodes[node_name]
                if node.type != type_to_remove:
                    continue
                self.remove_node(node)
                done = False

    def add_blob(self, name, shape, producer):
        new_blob = BLOB(name, shape, producer)
        self.__blobs[name] = new_blob
        log().debug('created:' + str(new_blob))
        return new_blob

    def add_edge(self, src, dst, blob):
        new_edge = Edge(src, dst, blob)
        self.__edges.append(new_edge)
        log().debug('created edge:' + str(new_edge))
        return new_edge

    def del_edge(self, edge_to_del):
        for edge in self.__edges:
            if edge == edge_to_del:
                log().debug("deleted edge: " + str(edge))
                self.__edges.remove(edge)
                return

    def get_start_node(self):
        #return self.__nodes.values()[0]
        return self.__first_node

    def find_blob_by_name(self, name):
        if name not in self.__blobs:
            return None
        return self.__blobs[name]

    def find_outgoing_edges(self, node):
        edges = []
        for edge in self.__edges:
            if (edge.is_deleted is False) and (edge.src_node != None) and (edge.src_node.name == node.name):
                edges.append(edge)
        return edges

    def find_incoming_edges(self, node):
        edges = []
        for edge in self.__edges:
            if (edge.is_deleted is False) and (edge.dst_node != None) and (edge.dst_node.name == node.name):
                edges.append(edge)
        return edges

    # Output BLOBs have no consumer and therefore they don't appear on an edge.
    # We scan all blobs, checking which blobs don't appear on an edge
    # TODO: THIS HAS A BUG (Works only the first time!!!!)
    def find_output_blobs(self):
        blobs = []
        for blob in self.__blobs:
            blob_has_consumer = False
            for edge in self.__edges:
                if edge.blob.name == blob:
                    blob_has_consumer = True
                    continue
            if blob_has_consumer is False:
                blobs.append(blob)
        return blobs

    def find_subgraph_pair(self, node1_type, node2_type):
        pairs = []
        for node_name in self.__nodes:
            # Search for a matching pair of nodes, by node types
            node1 = self.__nodes[node_name]
            if node1.type != node1_type:
                continue
            outgoing_edges = self.find_outgoing_edges(node1)
            assert len(outgoing_edges) == 1
            out_edge = outgoing_edges[0]
            if out_edge.dst_node is None or out_edge.dst_node.type != node2_type:
                continue

            # Found a match
            node2 = out_edge.dst_node
            pairs.append([node1, node2])
        return pairs

    def merge_nodes(self, node1_type, node2_type):
        ''' Merge two nodes together
        '''
        pairs = self.find_subgraph_pair(node1_type, node2_type)
        for (node1, node2) in pairs:
            new_node = PairNode(copy.deepcopy(node1), copy.deepcopy(node2))
            node2_outgoing_edges = self.find_outgoing_edges(node2)
            for node2_out_edge in node2_outgoing_edges:
                self.add_edge(new_node, node2_out_edge.dst_node, copy.deepcopy(node2_out_edge.blob))

            node1_incoming_edges = self.find_incoming_edges(node1)
            for node1_incoming_edge in node1_incoming_edges:
                self.add_edge(node1_incoming_edge.src_node, new_node, copy.deepcopy(node1_incoming_edge.blob))
            log().debug("[merge_nodes] deleting nodes %s, %s" % (node1.name,node2.name))
            self.del_nodes([node1, node2])
            self.add_nodes([new_node])
        return

    def traverse_blobs(self, blob_cb):
        done = []
        for blob in self.__blobs:
            if blob in done:
                continue
            blob_cb(self.__blobs[blob])

    def traverse(self, node_cb, edge_cb=None):
        """
        BFS (with modifications) traversal of the topology graph
        """
        pending = deque([self.get_start_node()])    # The list of nodes waiting to be processed
        done = []                                   # The list of nodes we've already processed
        log().debug('BFS: Starting traversal with node %s' % self.get_start_node())
        while len(pending) > 0:
            node = pending.popleft()

            # This is a modification of BFS: we mandate that all incoming edges
            # have been processed before processing the node to ensure processing order satisfies data dependency
            log().debug('BFS: processing node: %s' %node.name)
            incoming_edges = self.find_incoming_edges(node)
            all_in_edges_were_processed = True
            for edge in incoming_edges:
                if edge.src_node and edge.src_node not in done:
                    all_in_edges_were_processed = False
                    log().debug("BFS: %s is waiting for %s" % (node.name, edge.src_node.name))
            if all_in_edges_were_processed is False:
                continue

            done.append(node)
            log().debug("BFS: done with %s, total done %d, total pending %d" % (node.name, len(done), len(pending)) )
            if node_cb is not None:
                # TODO: this can probably be removed after adding the data-dependency constraint
                # Node callback can indicate failure, in which case we try again later
                cb_handled = node_cb(node)
                if cb_handled is False:
                    pending.append(node)
                    continue

            outgoing_edges = self.find_outgoing_edges(node)
            # Invoke the edge callback
            for edge in outgoing_edges:
                if edge_cb is not None:
                    exit = edge_cb(edge)
                    if exit:
                        log().debug("BFS: abrupt traversal exit requested by edge", str(edge))
                        return

            # Add new nodes to visit.  We do this as a separate step from the edge-callbacks,
            # because the edge-callbacks might alter the graph
            # outgoing_edges = self.find_outgoing_edges(node)
            outgoing_edges = self.find_outgoing_edges(node)
            for edge in outgoing_edges:
                if (edge.dst_node is not None) and (edge.dst_node not in done) and edge.dst_node not in pending:
                    pending.append(edge.dst_node)
                    log().debug('BFS: adding node: %s' % edge.dst_node.name)
                elif edge.dst_node is not None:
                    log().debug('BFS: ignoring  node: %s' % edge.dst_node.name)
        log().debug("BFS: traversal completed")
