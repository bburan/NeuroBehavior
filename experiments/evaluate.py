import ast
import numpy as np
from enthought.traits.ui.api import (TextEditor, View, Item, BooleanEditor,
        CompoundEditor)
from enthought.traits.api import Callable, HasTraits, Instance

'''
Available attributes for evaluating experiment parameters.

    random
        Numpy's random module.  Provides access to all the functions and
        distributions available within this module.
    arange
    randint(low, high)
        Return random integer within the range [low, high]
    uniform(low, high)
        Draw sample from uniform distribution in the interval [low, high)
    exponential(scale)
        Draw sample from exponential distribution with scale parameter (i.e.
        :math:`\\beta')
    clip(value, lb, ub)
        Ensure value falls within
        
    '''

class EvaluationError(NameError): pass

def choice(sequence):
    i = np.random.randint(0, len(sequence))
    return sequence[i]

def random_speaker(bias=0.5):
    return 'primary' if np.random.uniform() <= bias else 'secondary'

def get_dependencies(string):
    '''
    Parse a Python expression to determine what names are required to evaluate
    it.  Useful for determining dependencies.

    >>> get_dependencies('x+1')
    ('x',)

    >>> get_dependencies('32**0.5')
    ()

    >>> get_dependencies('sqrt(x)+y')
    ('sqrt', 'x', 'y')

    >>> get_dependencies('range(x)+numpy.random()')
    ('numpy', 'range', 'x')

    '''
    tree = ast.parse(string)
    result = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]
    result.sort()
    return tuple(result)

class ParameterExpression(object):

    GLOBALS = {
            'random':           np.random,
            'arange':           np.arange,
            'randint':          np.random.randint,
            'uniform':          np.random.uniform,
            'exponential':      np.random.exponential,
            'clip':             np.clip,
            'choice':           choice,
            'toss':             lambda x: np.random.uniform() <= x,
            'random_speaker':   random_speaker,
            }

    def __init__(self, value):
        if isinstance(value, basestring):
            self._expression = value
            self._code = compile(self._expression, '<string>', 'eval')
            self._dependencies = get_dependencies(self._expression)
            self._cache_valid = False
            self._cached_value = None

            try:
                # Do a quick check to see if any syntax errors pop out.
                # NameError is going to be a common one (especially when we are
                # making it dependent on other modules).  If we can successfully
                # evaluate it and it does not depend on any values, then we
                # might as well cache the resulting value.
                result = eval(self._code, self.GLOBALS)

                if not self._dependencies:
                    # If the code has no dependencies, then we can evaluate it
                    # once and use the cached value.  If the code has
                    # dependencies (even if it's in the globals dict, then we
                    # need to reevaluate it each time the value is requested
                    # just in case the globals function returns a random value).
                    self._cache_valid = True
                    self._cached_value = result
            except NameError:
                # This is the one error we will allow since it suggests the
                # expression requires values not present in the global
                # namespace.
                pass
        else:
            self._dependencies = []
            self._expression = str(value)
            self._cache_valid = True
            self._cached_value = value
            self._code = None

    def evaluate(self, local_context=None):
        if self._cache_valid:
            return self._cached_value
        else:
            return eval(self._code, self.GLOBALS, local_context)

    def __str__(self):
        return self._expression

    def __repr__(self):
        return "{} ({})".format(self._expression, self._cache_valid)

    # One must define both the == and != rich comparision methods for
    # on_trait_change to properly register trait changes while ignoring
    # situations where two ParameterExpressions have identical values.
    def __eq__(self, other):
        if not isinstance(other, ParameterExpression):
            return NotImplemented
        return self._expression == other._expression

    def __ne__(self, other):
        if not isinstance(other, ParameterExpression):
            return NotImplemented
        return self._expression != other._expression

    def __getstate__(self):
        '''
        Code objects cannot be pickled
        '''
        state = self.__dict__.copy()
        del state['_code']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if not self._cache_valid:
            self._code = compile(self._expression, '<string>', 'eval')
        else:
            self._code = None

def evaluate_value(parameter, expressions, context=None):
    '''
    Given a stack of expressions and the desired parameter to evaluate,
    evaluates all the expressions necessary to evaluate the desired parameter.
    If an expression is evaluated, it is removed from the stack of expressions
    and added to the context.
    '''
    try:
        if context is None:
            context = {}

        if parameter in context:
            del expressions[parameter]
            return context

        expression = expressions[parameter]
        del expressions[parameter]

        if isinstance(expression, ParameterExpression):
            for d in expression._dependencies:
                if d in expressions:
                    evaluate_value(d, expressions, context)
            context[parameter] = expression.evaluate(context)
        else:
            context[parameter] = expression
        return context
    except EvaluationError, e:
        # Add an empty catch block here because EvaluationError is a subclass of
        # NameError and we only want to catch explicit instances of NameError so
        # we can convert them to EvaluationErrors.
        raise
    except NameError, e:
        # Catch NameErrors and convert them to EvaluationErrors
        mesg = """
        Unable to evaluate '{}' because {} or has a circular reference (either
        directly or indirectly via other variables) to '{}'"""
        import textwrap
        mesg = textwrap.dedent(mesg).strip().replace('\n', ' ')
        raise EvaluationError, mesg.format(parameter, e, parameter)

def evaluate_expressions(expressions, current_context):
    '''
    Will raise a NameError if it is no longer able to evaluate.
    '''
    while expressions:
        name = expressions.keys()[0]
        evaluate_value(name, expressions, current_context)

class ExpressionEditor(TextEditor):

    evaluate = Callable(ParameterExpression)

from enthought.traits.api import TraitType

class Expression(TraitType):

    def validate(self, object, name, value):
        if isinstance(value, ParameterExpression):
            return value
        self.error(object, name, value)

    def create_editor(self):
        return ExpressionEditor()

    def init(self):
        if not isinstance(self.default_value, ParameterExpression):
            self.default_value = ParameterExpression(self.default_value)

import unittest

class TestExpressions(unittest.TestCase):

    parameters = {
            'a':    ParameterExpression('5'),
            'b':    ParameterExpression('6'),
            'c':    ParameterExpression('a*5'),
            'd':    ParameterExpression('a*b+c'),
            'e':    ParameterExpression('d+c'),
            'f':    ParameterExpression('1.23'),
            'g':    ParameterExpression('range(a, b)'),
            'h':    ParameterExpression('randint(5, 6)'),
            'i':    ParameterExpression('uniform(1, 5)'),
            #'j':    ParameterExpression('l'),
            'j':    57,
            'k':    65,
            'l':    ParameterExpression('j+k'),
            }

    evaluate_value_tests = [
            ('a', {}, {'a': 5}),
            ('b', {}, {'b': 6}),
            ('c', {}, {'a': 5, 'c': 25}),
            ('d', {}, {'a': 5, 'b': 6, 'c': 25, 'd': 55}),
            ('d', {'a': 4}, {'a': 4, 'b': 6, 'c': 20, 'd': 44}),
            ('h', {}, {'h': 5}),
            ]

    def test_evaluate_value(self):
        for parameter, extra_context, expected in self.evaluate_value_tests:
            parameters = self.parameters.copy()
            actual = evaluate_value(parameter, parameters, extra_context)
            self.assertEqual(expected, actual)

            for parameter in expected:
                self.assertTrue(parameter not in parameters)

    def test_equal(self):
        a = ParameterExpression('a+b')
        b = ParameterExpression('a+b')
        self.assertEqual(a, b)

from enthought.traits.api import HasTraits, on_trait_change
class TestTraits(HasTraits):
     
    a = Instance(ParameterExpression, ('a+4',))

    @on_trait_change('a')
    def print_change(self):
        print 'changed'


if __name__ == '__main__':
    #parameters = {'a': ParameterExpression('1'), 'b': ParameterExpression('a')}
    #evaluate_value('a', parameters)
    #context = {}
    #evaluate_expressions(parameters, context)
    #print parameters, context
    #import doctest
    #doctest.testmod()
    #unittest.main()
    t = TestTraits()
    print 'assinging'
    t.a = ParameterExpression('b+4')
    print 'assinging'
    t.a = ParameterExpression('b+4')
    print 'assinging'
    t.a = ParameterExpression('b+4')