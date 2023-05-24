"""
Simplified VM code which works for some cases.
You need extend/rewrite code to pass all cases.
"""

import builtins
import dis
import types
import typing as tp
import operator

CO_VARARGS = 4
CO_VARKEYWORDS = 8


class Frame:

    """
    Frame header in cpython with description
        https://github.com/python/cpython/blob/3.10/Include/frameobject.h

    Text description of frame parameters
        https://docs.python.org/3/library/inspect.html?highlight=frame#types-and-members
    """

    COMPARE_OPS = {
        '<': operator.lt,
        '<=': operator.le,
        '==': operator.eq,
        '!=': operator.ne,
        '>': operator.gt,
        '>=': operator.ge,
    }

    def __init__(self,
                 frame_code: types.CodeType,
                 frame_builtins: dict[str, tp.Any],
                 frame_globals: dict[str, tp.Any],
                 frame_locals: dict[str, tp.Any]) -> None:
        self.code = frame_code
        self.builtins = frame_builtins
        self.globals = frame_globals
        self.locals = frame_locals
        self.data_stack: tp.Any = []
        self.return_value = None
        self.counter = 0
        self.last_exception: list[tp.Any] = []
        self.jump: tp.Union[int, None] = None
        self.bytecode_len: int = 0
        self.load_comprehension = False

    def nop_op(self, arg: tp.Any) -> tp.Any:
        pass

    def top(self) -> tp.Any:
        return self.data_stack[-1]

    def peek(self, i: int) -> tp.Any:
        return self.data_stack[i]

    def pop(self) -> tp.Any:
        return self.data_stack.pop()

    def push(self, *values: tp.Any) -> None:
        self.data_stack.extend(values)

    def popn(self, n: int) -> tp.Any:
        """
        Pop a number of values from the value stack.
        A list of n values is returned, the deepest value first.
        """
        if n > 0:
            returned = self.data_stack[-n:]
            self.data_stack[-n:] = []
            return returned
        else:
            return []

    def run(self) -> tp.Any:
        instructions = tuple(dis.get_instructions(self.code))
        self.bytecode_len = 2 * len(instructions)
        self.counter = 0
        while self.counter < self.bytecode_len:
            instruction = instructions[self.counter // 2]
            getattr(self, instruction.opname.lower() + "_op")(instruction.argval)
            if isinstance(self.jump, int):
                self.counter = self.jump
                self.jump = None
            else:
                self.counter += 2
        return self.return_value

    def load_name_op(self, arg: str) -> None:
        """
        Partial realization

        Operation description:
            https://docs.python.org/release/3.10.6/library/dis.html#opcode-LOAD_NAME

        Operation realization:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#L2829
        """
        # TODO: parse all scopes
        if arg in self.locals:
            self.push(self.locals[arg])
        elif arg in self.globals:
            self.push(self.globals[arg])
        elif arg in self.builtins:
            self.push(self.builtins[arg])
        else:
            raise NameError(
                f'Variable "{arg}" does not exist'
            )

    def import_name_op(self, name: str) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(__import__(name, self.globals, self.locals, tos, tos1))

    def import_from_op(self, name: str) -> tp.Any:
        tos = self.top()
        self.push(getattr(tos, name))

    def import_star_op(self, arg: tp.Any) -> tp.Any:
        tos = self.pop()
        for name in dir(tos):
            if name[0] != '_':
                self.locals[name] = getattr(tos, name)

    def store_attr_op(self, name: str) -> tp.Any:
        tos1, tos = self.popn(2)
        setattr(tos, name, tos1)

    def dup_top_op(self, arg: tp.Any) -> tp.Any:
        self.push(self.top())

    def dup_top_two_op(self, arg: tp.Any) -> tp.Any:
        self.push(* self.popn(2) * 2)

    def load_attr_op(self, name: str) -> tp.Any:
        tos = self.pop()
        self.push(getattr(tos, name))

    def delete_attr_op(self, name: str) -> tp.Any:
        tos = self.pop()
        delattr(tos, name)

    def delete_name_op(self, namei: str) -> tp.Any:
        del self.globals[namei]

    def delete_fast_op(self, namei: str) -> tp.Any:
        del self.locals[namei]

    def store_global_op(self, arg: str) -> tp.Any:
        self.globals[arg] = self.pop()

    def compare_op_op(self, opname: str) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(self.COMPARE_OPS[opname](tos1, tos))

    def contains_op_op(self, invert: int) -> tp.Any:
        tos1, tos = self.popn(2)
        if invert == 1:
            self.push(tos1 not in tos)
        else:
            self.push(tos1 in tos)

    def is_op_op(self, invert: int) -> tp.Any:
        tos1, tos = self.popn(2)
        if invert == 1:
            self.push(tos1 is not tos)
        else:
            self.push(tos1 is tos)

    def pop_jump_if_true_op(self, target: int) -> tp.Any:
        if self.pop():
            self.jump = target

    def pop_jump_if_false_op(self, target: int) -> tp.Any:
        if not self.pop():
            self.jump = target

    def jump_if_true_or_pop_op(self, target: int) -> tp.Any:
        if self.top():
            self.jump = target
        else:
            self.pop()

    def jump_if_false_or_pop_op(self, target: int) -> tp.Any:
        if not self.top():
            self.jump = target
        else:
            self.pop()

    def jump_forward_op(self, delta: int) -> tp.Any:
        self.jump = delta

    def unary_positive_op(self, arg: tp.Any) -> tp.Any:
        self.push(+self.pop())

    def unary_negative_op(self, arg: tp.Any) -> tp.Any:
        self.push(-self.pop())

    def unary_invert_op(self, arg: tp.Any) -> tp.Any:
        self.push(~self.pop())

    def unary_not_op(self, arg: tp.Any) -> tp.Any:
        self.push(not self.pop())

    def binary_add_op(self, arg: str) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 + tos)

    def binary_subtract_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 - tos)

    def binary_xor_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 ^ tos)

    def binary_or_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 | tos)

    def binary_and_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 & tos)

    def binary_power_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 ** tos)

    def binary_floor_divide_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 // tos)

    def binary_modulo_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 % tos)

    def binary_multiply_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 * tos)

    def binary_lshift_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 << tos)

    def binary_rshift_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 >> tos)

    def binary_true_divide_op(self, arg: str) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 / tos)

    def binary_matrix_multiply(self, arg: str) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1 @ tos)

    def load_build_class_op(self, arg: tp.Any) -> tp.Any:
        self.push(self.builtins['__build_class__'])

# INPLACE ~~~~~~~~~~~~

    def inplace_power_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1**tos
        self.push(tos)

    def inplace_multiply_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 * tos
        self.push(tos)

    def inplace_floor_divide_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 // tos
        self.push(tos)

    def inplace_modulo_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 % tos
        self.push(tos)

    def inplace_subtract_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 - tos
        self.push(tos)

    def inplace_lshift_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 << tos
        self.push(tos)

    def inplace_rshift_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 >> tos
        self.push(tos)

    def inplace_and_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 & tos
        self.push(tos)

    def inplace_or_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 | tos
        self.push(tos)

    def inplace_xor_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 ^ tos
        self.push(tos)

    def inplace_add_op(self, arg: str) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 + tos
        self.push(tos)

    def inplace_true_divide_op(self, arg: str) -> tp.Any:
        tos1, tos = self.popn(2)
        tos = tos1 / tos
        self.push(tos)

    def load_assertion_error_op(self, arg: str) -> tp.Any:
        self.push(AssertionError)

    def raise_varargs_op(self, argc: int) -> tp.Any:
        exctype = val = tb = None
        if argc == 0:
            exctype, val, tb = self.last_exception
        elif argc == 1:
            exctype = self.pop()
        elif argc == 2:
            val = self.pop()
            exctype = self.pop()
        elif argc == 3:
            tb = self.pop()
            val = self.pop()
            exctype = self.pop()

        # There are a number of forms of "raise", normalize them somewhat.
        if isinstance(exctype, BaseException):
            val = exctype
            exctype = type(val)

        self.last_exception = [exctype, val, tb]

        if tb:
            return 'reraise'
        else:
            return 'exception'

# ITERS ~~~~~~~~~~~~~~~

    def build_slice_op(self, argc: int) -> tp.Any:
        if argc == 2:
            tos1, tos = self.popn(2)
            self.push(slice(tos1, tos))
        elif argc == 3:
            tos2, tos1, tos = self.popn(3)
            self.push(slice(tos2, tos1, tos))

    def for_iter_op(self, delta: int) -> tp.Any:
        try:
            self.push(next(self.top()))
        except StopIteration:
            self.pop()
            self.jump = delta

    def gen_start_op(self, kind: int) -> tp.Any:
        pass

    def yield_value_op(self, arg: tp.Any) -> tp.Any:
        self.pop()

    # def yield_from_op(self, arg: tp.Any):
    #     u = self.pop()
    #     x = self.top()
    #
    #     try:
    #         if not isinstance(x, types.GeneratorType) or u is None:
    #             # Call next on iterators.
    #             retval = next(x)
    #         else:
    #             retval = x.send(u)
    #         self.return_value = retval
    #     except StopIteration as e:
    #         self.pop()
    #         self.push(e.value)

    def get_yield_from_iter_op(self, arg: tp.Any) -> tp.Any:
        tos = self.pop()
        if isinstance(tos, types.GeneratorType):
            self.push(tos)
        else:
            self.push(iter(self.pop()))

    def jump_absolute_op(self, target: int) -> tp.Any:
        self.jump = target

    def get_iter_op(self, arg: tp.Any) -> tp.Any:
        self.push(iter(self.pop()))

    def unpack_sequence_op(self, arg: tp.Any) -> tp.Any:
        packed = self.pop()
        self.push(*packed[::-1])

    def build_set_op(self, count: int) -> tp.Any:
        self.push(set(self.popn(count)))

    def set_add_op(self, i: int) -> tp.Any:
        tos = self.pop()
        set.add(self.peek(-i), tos)

    def set_update_op(self, i: int) -> tp.Any:
        tos = self.pop()
        set.update(self.peek(-i), tos)

    def build_tuple_op(self, count: int) -> tp.Any:
        self.push(tuple(self.popn(count)))

    def build_list_op(self, count: int) -> tp.Any:
        self.push(list(self.popn(count)))

    def rot_two_op(self, arg: tp.Any) -> tp.Any:
        self.push(*self.popn(2)[::-1])

    def rot_three_op(self, arg: tp.Any) -> tp.Any:
        tos2, tos1, tos = self.popn(3)
        self.push(tos, tos2, tos1)

    def rot_n_op(self, count: int) -> tp.Any:
        tos = self.pop()
        toses = self.popn(count)
        self.push(tos)
        self.push(*toses)

    def get_len_op(self, arg: tp.Any) -> tp.Any:
        self.push(len(self.pop()))

    def binary_subscr_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        self.push(tos1[tos])

    def store_subscr_op(self, arg: tp.Any) -> tp.Any:
        tos2, tos1, tos = self.popn(3)
        tos1[tos] = tos2

    def delete_subscr_op(self, arg: tp.Any) -> tp.Any:
        tos1, tos = self.popn(2)
        del tos1[tos]

    def build_string_op(self, count: int) -> tp.Any:
        self.push(''.join(self.popn(count)))

    def build_map_op(self, count: int) -> tp.Any:
        toses = self.popn(2 * count)
        self.push({toses[i]: toses[i + 1] for i in range(2 * count - 1)})

    def map_add_op(self, i: int) -> tp.Any:
        tos1, tos = self.popn(2)
        dict.__setitem__(self.peek(-i), tos1, tos)

    def build_const_key_map_op(self, count: int) -> tp.Any:
        const_keys = self.pop()
        values = self.popn(count)
        self.push({k: v for k, v in zip(const_keys, values)})

    def load_method_op(self, name: str) -> tp.Any:
        self.push(getattr(self.pop(), name))

    def load_global_op(self, arg: str) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.10.6/library/dis.html#opcode-LOAD_GLOBAL

        Operation realization:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#L2958
        """
        # TODO: parse all scopes

        if arg in self.globals:
            self.push(self.globals[arg])
        elif arg in self.builtins:
            self.push(self.builtins[arg])
        else:
            raise NameError(
                f'Global variable "{arg}" referenced before assignment'
            )

    # def format_value_op(self, flags: tp.Any) -> tp.Any:
    #    print('smth')

    def load_fast_op(self, arg: tp.Any) -> None:
        if arg in ('.0', '.1', '.2'):
            self.push(iter(self.top()))
        elif arg in self.locals:
            self.push(self.locals[arg])
        else:
            raise UnboundLocalError(
                f'local variable "{arg}" referenced before assignment'
            )

    def load_const_op(self, arg: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.10.6/library/dis.html#opcode-LOAD_CONST

        Operation realization:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#L1871
        """
        self.push(arg)

    def return_value_op(self, arg: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.10.6/library/dis.html#opcode-RETURN_VALUE

        Operation realization:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#L2436
        """
        self.return_value = self.pop()
        self.counter = self.bytecode_len

    def pop_top_op(self, arg: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.10.6/library/dis.html#opcode-POP_TOP

        Operation realization:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#L1886
        """
        self.pop()

    def call_function_op(self, arg: int) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.10.6/library/dis.html#opcode-CALL_FUNCTION

        Operation realization:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#4243
        """
        arguments = self.popn(arg)
        f = self.pop()
        self.push(f(*arguments))

    def call_function_kw_op(self, arg: int) -> tp.Any:
        kw_names = self.pop()
        kw_values = self.popn(len(kw_names))
        kwargs = {k: v for k, v in zip(kw_names, kw_values)}
        posargs = self.popn(arg - len(kw_names))
        f = self.pop()
        self.push(f(*posargs, **kwargs))

    def make_function_op(self, arg: int) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.10.6/library/dis.html#opcode-MAKE_FUNCTION

        Operation realization:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#L4290

        Parse stack:
            https://github.com/python/cpython/blob/3.10/Objects/call.c#L612

        Call function in cpython:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#L4209
        """
        name = self.pop()  # the qualified name of the function (at TOS)  # noqa
        code = self.pop()  # the code associated with the function (at TOS1)
        # TODO: use arg to parse function defaults
        defaults = self.popn(arg)

        def f(*args: tp.Any, **kwargs: tp.Any) -> tp.Any:
            # TODO: parse input arguments using code attributes such as co_argcount
            has_varargs = bool(code.co_flags & CO_VARARGS)
            has_varkwargs = bool(code.co_flags & CO_VARKEYWORDS)

            posonly_slice = slice(None, code.co_posonlyargcount)
            pos_or_kw_slice = slice(code.co_posonlyargcount, code.co_argcount)
            kwonly_slice = slice(code.co_argcount, code.co_argcount + code.co_kwonlyargcount)
            defaults_slice = slice(code.co_kwonlyargcount - len(defaults), code.co_argcount)

            defaults_names = code.co_varnames[defaults_slice]
            default = dict(zip(defaults_names, defaults))

            parsed_posonlyargs = dict(zip(code.co_varnames[posonly_slice], args[posonly_slice]))
            parsed_posargs = dict(zip(code.co_varnames[pos_or_kw_slice], args[pos_or_kw_slice]))

            varargs = args[code.co_argcount:]

            # posonly_names = frozenset(code.co_varnames[posonly_slice])
            pos_or_kw_names = frozenset(code.co_varnames[pos_or_kw_slice])
            kwonly_names = frozenset(code.co_varnames[kwonly_slice])

            parsed_kwargs: dict[str, tp.Any] = {}
            parsed_kwonlyargs: dict[str, tp.Any] = {}
            varkwargs: dict[str, tp.Any] = {}

            for k, v in kwargs.items():
                if k in pos_or_kw_names:
                    parsed_kwargs[k] = v
                elif k in kwonly_names:
                    parsed_kwonlyargs[k] = v
                else:
                    varkwargs[k] = v
            parsed_args: dict[str, tp.Any] = default
            parsed_args.update({**parsed_posonlyargs, **parsed_posargs, **parsed_kwargs, **parsed_kwonlyargs})

            if has_varargs:
                varargs_name = code.co_varnames[code.co_argcount + code.co_kwonlyargcount]
                parsed_args[varargs_name] = varargs
            if has_varkwargs:
                varkwargs_name = code.co_varnames[code.co_argcount + code.co_kwonlyargcount + has_varargs]
                parsed_args[varkwargs_name] = varkwargs

            f_locals = dict(self.locals)
            f_locals.update(parsed_args)

            frame = Frame(code, self.builtins, self.globals, f_locals)  # Run code in prepared environment
            return frame.run()
        f.__qualname__ = name
        self.push(f)

    def store_fast_op(self, arg: str) -> None:
        self.locals[arg] = self.pop()

    def store_name_op(self, arg: str) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.10.6/library/dis.html#opcode-STORE_NAME

        Operation realization:
            https://github.com/python/cpython/blob/3.10/Python/ceval.c#L2758
        """
        const = self.pop()
        self.locals[arg] = const

    def list_to_tuple_op(self, arg: tp.Any) -> tp.Any:
        self.push(tuple(self.pop()))

    def list_extend_op(self, i: int) -> tp.Any:
        tos = self.pop()
        list.extend(self.peek(-i), tos)

    def list_append_op(self, i: int) -> tp.Any:
        tos = self.pop()
        list.append(self.peek(-i), tos)


class VirtualMachine:
    def run(self, code_obj: types.CodeType) -> None:
        """
        :param code_obj: code for interpreting
        """
        globals_context: dict[str, tp.Any] = {}
        frame = Frame(code_obj, builtins.globals()['__builtins__'], globals_context, globals_context)
        return frame.run()
