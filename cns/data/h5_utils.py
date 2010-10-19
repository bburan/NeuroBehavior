'''
Created on Jul 20, 2010

@author: Brad
'''
import tables
import logging
log = logging.getLogger(__name__)

name_lookup = {'group':     'Group',
               'earray':    'EArray',
               'array':     'Array',
               'table':     'Table'}

def get_or_append_node(node, name, type='group', *arg, **kw):
    try:
        # TODO: add type checking?
        return getattr(node, name)
    except tables.NoSuchNodeError:
        return append_node(node, name, type, *arg, **kw)

def append_node(node, name, type='group', *arg, **kw):
    log.debug('appending %r to node %r', name, node._v_pathname)
    file = node._v_file
    path = node._v_pathname
    type = name_lookup[type.lower()]
    func = getattr(file, 'create' + type)
    new_node = func(path, name, *arg, **kw)
    #file.flush()
    return new_node

time_fmt = '%Y_%m_%d_%H_%M_%S'

def extract_date_from_name(node, pre='date', post=''):
    from datetime import datetime
    import re
    name = node._v_name
    string = re.sub('^'+pre, '', name)
    string = re.sub(post+'$', '', string)
    return datetime.strptime(string, time_fmt)
    
def append_date_node(node, pre='date', post='', type='group', *arg, **kw):
    from datetime import datetime
    name = pre + datetime.now().strftime(time_fmt) + post
    return append_node(node, name, type, *arg, **kw)



import re
_METADATA_PATTERN = re.compile('^_v_')

def node_match(n, **kw):
    '''Checks for match against each keyword.  If an attribute is missing or
    any match fails, returns False.
    '''

    for k, v in kw.items():
        try:
            if _METADATA_PATTERN.match(k):
                value = getattr(n, k)
            else:
                value = getattr(n._v_attrs, k)
            if type(v) == type(''):
                if re.match(v, value) is None:
                    return False
            else:
                if v != value:
                    return False
        except AttributeError:
            return False
    return True

def _walk(where, mode, **kw):
    '''Recursively returns all nodes hanging off of the starting node that match
    the given criteria.

    Criteria can be specified as keyword arguments where the keyword indicates
    the attribute.  The keyword can either be one of the node's special
    attributes (e.g. _v_pathname or _v_name) or a user-set attribute.  The value
    may be a regular expression as well.

    Hint, to limit to a given depth, use the _v_depth attribute (you may have to
    account for the starting depth, not sure as I have never used this feature).

    Returns
    -------
    iterable

    For a non-recursive version, see `list_nodes`.  Use the non-recursive
    version where possible as it will be much faster. 

    To return all nodes with the attribute klass='Animal'
    >>> fh = tables.openFile('example_data.h5', 'r')
    >>> animal_nodes = [n for n in walk_nodes(fh.root, klass='Animal')]

    To return all nodes whose name matches a given partern
    >>> fh = tables.openFile('example_data.h5', 'r')
    >>> animal_nodes = [n for n in walk_nodes(fh.root, _v_name='^Animal_\d+')]
    '''
    for node in getattr(where, mode)():
        if node_match(node, **kw):
            yield node

from functools import partial

walk_nodes = partial(_walk, mode='_f_walkNodes')
iter_nodes = partial(_walk, mode='_f_iterNodes')
