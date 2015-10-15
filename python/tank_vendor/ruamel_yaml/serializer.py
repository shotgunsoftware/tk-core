from __future__ import absolute_import

__all__ = ['Serializer', 'SerializerError']

import re

from .error import YAMLError
from .events import *
from .nodes import *

from .compat import nprint, DBG_NODE, dbg


class SerializerError(YAMLError):
    pass


class Serializer(object):

    # 'id' and 3+ numbers, but not 000
    ANCHOR_TEMPLATE = u'id%03d'
    ANCHOR_RE = re.compile(u'id(?!000$)\\d{3,}')


    def __init__(self, encoding=None, explicit_start=None, explicit_end=None,
                 version=None, tags=None):
        self.use_encoding = encoding
        self.use_explicit_start = explicit_start
        self.use_explicit_end = explicit_end
        self.use_version = version
        self.use_tags = tags
        self.serialized_nodes = {}
        self.anchors = {}
        self.last_anchor_id = 0
        self.closed = None
        self._templated_id = None

    def open(self):
        if self.closed is None:
            self.emit(StreamStartEvent(encoding=self.use_encoding))
            self.closed = False
        elif self.closed:
            raise SerializerError("serializer is closed")
        else:
            raise SerializerError("serializer is already opened")

    def close(self):
        if self.closed is None:
            raise SerializerError("serializer is not opened")
        elif not self.closed:
            self.emit(StreamEndEvent())
            self.closed = True

    # def __del__(self):
    #     self.close()

    def serialize(self, node):
        if dbg(DBG_NODE):
            nprint('Serializing nodes')
            node.dump()
        if self.closed is None:
            raise SerializerError("serializer is not opened")
        elif self.closed:
            raise SerializerError("serializer is closed")
        self.emit(DocumentStartEvent(explicit=self.use_explicit_start,
                                     version=self.use_version,
                                     tags=self.use_tags))
        self.anchor_node(node)
        self.serialize_node(node, None, None)
        self.emit(DocumentEndEvent(explicit=self.use_explicit_end))
        self.serialized_nodes = {}
        self.anchors = {}
        self.last_anchor_id = 0

    def anchor_node(self, node):
        if node in self.anchors:
            if self.anchors[node] is None:
                self.anchors[node] = self.generate_anchor(node)
        else:
            anchor = None
            try:
                if node.anchor.always_dump:
                    anchor = node.anchor.value
            except:
                pass
            self.anchors[node] = anchor
            if isinstance(node, SequenceNode):
                for item in node.value:
                    self.anchor_node(item)
            elif isinstance(node, MappingNode):
                for key, value in node.value:
                    self.anchor_node(key)
                    self.anchor_node(value)

    def generate_anchor(self, node):
        try:
            anchor = node.anchor.value
        except:
            anchor = None
        if anchor is None:
            self.last_anchor_id += 1
            return self.ANCHOR_TEMPLATE % self.last_anchor_id
        return anchor

    def serialize_node(self, node, parent, index):
        alias = self.anchors[node]
        if node in self.serialized_nodes:
            self.emit(AliasEvent(alias))
        else:
            self.serialized_nodes[node] = True
            self.descend_resolver(parent, index)
            if isinstance(node, ScalarNode):
                detected_tag = self.resolve(ScalarNode, node.value,
                                            (True, False))
                default_tag = self.resolve(ScalarNode, node.value,
                                           (False, True))
                implicit = \
                    (node.tag == detected_tag), (node.tag == default_tag)
                self.emit(ScalarEvent(alias, node.tag, implicit, node.value,
                                      style=node.style, comment=node.comment))
            elif isinstance(node, SequenceNode):
                implicit = (node.tag
                            == self.resolve(SequenceNode, node.value, True))
                comment = node.comment
                # print('comment >>>>>>>>>>>>>.', comment, node.flow_style)
                end_comment = None
                seq_comment = None
                if node.flow_style is True:
                    if comment:  # eol comment on flow style sequence
                        seq_comment = comment[0]
                        # comment[0] = None
                if comment and len(comment) > 2:
                    end_comment = comment[2]
                else:
                    end_comment = None
                self.emit(SequenceStartEvent(alias, node.tag, implicit,
                                             flow_style=node.flow_style,
                                             comment=node.comment))
                index = 0
                for item in node.value:
                    self.serialize_node(item, node, index)
                    index += 1
                self.emit(SequenceEndEvent(comment=[seq_comment, end_comment]))
            elif isinstance(node, MappingNode):
                implicit = (node.tag
                            == self.resolve(MappingNode, node.value, True))
                comment = node.comment
                end_comment = None
                map_comment = None
                if node.flow_style is True:
                    if comment:  # eol comment on flow style sequence
                        map_comment = comment[0]
                        # comment[0] = None
                if comment and len(comment) > 2:
                    end_comment = comment[2]
                self.emit(MappingStartEvent(alias, node.tag, implicit,
                                            flow_style=node.flow_style,
                                            comment=node.comment))
                for key, value in node.value:
                    self.serialize_node(key, node, None)
                    self.serialize_node(value, node, key)
                self.emit(MappingEndEvent(comment=[map_comment, end_comment]))
            self.ascend_resolver()

def templated_id(s):
    return Serializer.ANCHOR_RE.match(s)