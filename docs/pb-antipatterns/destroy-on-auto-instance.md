# `destroy <name>` on a global auto-instance shadowing a field

## Smell

```pb
// global auto-instance declared somewhere:
//   global n_logger n_logger
//
// inside an object that holds a private logger field:
forward
public:
    n_logger n_logger
end forward

protected function long shutdown()
    if isvalid(n_logger) then
        destroy n_logger      // ← which n_logger?
    end if
    return 0
end function
```

## Why it bites

PowerScript's name resolution for `destroy <identifier>` walks the
scope chain just like a read access would. When a class has a
private field with the **same name** as a global auto-instance,
the local field shadows the global only in expressions; but
`destroy` on the bare name targets the resolution that wins at
that point of the source — which, depending on the declaration
order and the type vs. variable disambiguation, can be the global
auto-instance instead of the field.

The net effect: a method that thinks it is freeing its own private
logger ends up destroying the application-wide singleton. Every
subsequent call to anything that relies on the global blows up
with a null-object error far away from the destruction site, so
the symptom is decoupled from the cause and the bug is painful to
diagnose.

## Idiomatic fix

```pb
protected function long shutdown()
    if isvalid(this.n_logger) then
        destroy this.n_logger    // ← unambiguous: the field
    end if
    return 0
end function
```

Use `this.<field>` (or, in inherited classes, the explicit instance
qualifier) for `destroy` whenever a field shadows a same-named
global or type. The `this.` prefix forces the local field
resolution and removes any ambiguity for the human reader as well.

Even better: avoid the same-name shadowing in the first place.
Field naming conventions (`inv_log` for instance NVO, `iuo_log`
for instance userobject) keep field names distinct from type names
and from global auto-instances.

## Where it has been seen

- `rstpb22` chain of `n_logger` (review run 2026-05-20): private
  field shared the name `n_logger` with the global auto-instance;
  `destroy n_logger` in the destructor chain killed the global,
  causing subsequent log calls in unrelated modules to fail with
  a null reference.

## Related

- [exitprocess in destruction chain](exitprocess-in-destruction.md) —
  another "destroy thinks it's local, actually it's global" failure.
