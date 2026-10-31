package dev.daeloryn.analysis;

import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.nio.file.*;
import java.util.*;
import javax.lang.model.element.*;
import javax.lang.model.util.Elements;
import javax.tools.*;

/** Compiler-resolved source index. Never generates or executes project bytecode. */
public final class ImpactIndex {
    private static String json(String text) {
        if (text == null) return "null";
        StringBuilder out = new StringBuilder("\"");
        for (char c : text.toCharArray()) {
            if (c == '"' || c == '\\') out.append('\\').append(c);
            else if (c < 32) out.append(String.format("\\u%04x", (int)c));
            else out.append(c);
        }
        return out.append('"').toString();
    }
    private static String symbol(Element element, Elements elements) {
        if (element instanceof TypeElement) return elements.getBinaryName((TypeElement)element).toString();
        if (element instanceof ExecutableElement) {
            ExecutableElement method = (ExecutableElement)element;
            StringJoiner parameters = new StringJoiner(",");
            for (VariableElement p : method.getParameters()) parameters.add(p.asType().toString());
            return symbol(method.getEnclosingElement(), elements) + "#" + method.getSimpleName()
                + "(" + parameters + ")";
        }
        if (element != null && (element.getKind() == ElementKind.FIELD || element.getKind() == ElementKind.ENUM_CONSTANT))
            return symbol(element.getEnclosingElement(), elements) + "#" + element.getSimpleName();
        return null;
    }
    public static void main(String[] args) throws Exception {
        Path root = Paths.get(args[0]).toRealPath();
        String release = args[1];
        String classpath = args[2];
        List<String> names = Arrays.asList(args).subList(3, args.length);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) throw new IllegalStateException("JDK compiler required");
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<JavaFileObject>();
        List<String> definitions = new ArrayList<String>();
        Set<String> references = new LinkedHashSet<String>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, Locale.ROOT, java.nio.charset.StandardCharsets.UTF_8)) {
            manager.setLocation(StandardLocation.SOURCE_PATH, Collections.<java.io.File>emptyList());
            List<String> options = Arrays.asList("--release", release, "-proc:none", "-implicit:none", "-classpath", classpath);
            JavacTask task = (JavacTask)compiler.getTask(null, manager, diagnostics, options, null,
                manager.getJavaFileObjectsFromStrings(names));
            List<CompilationUnitTree> units = new ArrayList<CompilationUnitTree>();
            for (CompilationUnitTree unit : task.parse()) units.add(unit);
            task.analyze();
            final Trees trees = Trees.instance(task);
            final Elements elements = task.getElements();
            for (final CompilationUnitTree unit : units) {
                final String path = root.relativize(Paths.get(unit.getSourceFile().toUri()).toRealPath()).toString().replace('\\', '/');
                new TreePathScanner<Void, String>() {
                    private String define(Tree node) {
                        Element element = trees.getElement(getCurrentPath());
                        String id = symbol(element, elements);
                        long start = trees.getSourcePositions().getStartPosition(unit, node);
                        if (id != null && start >= 0) {
                            definitions.add("{\"symbol\":" + json(id) + ",\"path\":" + json(path)
                                + ",\"line\":" + unit.getLineMap().getLineNumber(start) + "}");
                        }
                        return id;
                    }
                    private void reference(Tree node, String owner) {
                        String target = symbol(trees.getElement(getCurrentPath()), elements);
                        long start = trees.getSourcePositions().getStartPosition(unit, node);
                        if (owner != null && target != null && start >= 0 && !owner.equals(target)) {
                            references.add("{\"owner\":" + json(owner) + ",\"target\":" + json(target)
                                + ",\"path\":" + json(path) + ",\"line\":" + unit.getLineMap().getLineNumber(start) + "}");
                        }
                    }
                    @Override public Void visitClass(ClassTree node, String owner) {
                        return super.visitClass(node, define(node));
                    }
                    @Override public Void visitMethod(MethodTree node, String owner) {
                        return super.visitMethod(node, define(node));
                    }
                    @Override public Void visitVariable(VariableTree node, String owner) {
                        Element element = trees.getElement(getCurrentPath());
                        String field = symbol(element, elements);
                        return super.visitVariable(node, field == null ? owner : define(node));
                    }
                    @Override public Void visitIdentifier(IdentifierTree node, String owner) {
                        reference(node, owner); return super.visitIdentifier(node, owner);
                    }
                    @Override public Void visitNewClass(NewClassTree node, String owner) {
                        reference(node, owner); return super.visitNewClass(node, owner);
                    }
                    @Override public Void visitMemberReference(MemberReferenceTree node, String owner) {
                        reference(node, owner); return super.visitMemberReference(node, owner);
                    }
                    @Override public Void visitMemberSelect(MemberSelectTree node, String owner) {
                        reference(node, owner); return super.visitMemberSelect(node, owner);
                    }
                }.scan(unit, null);
            }
        }
        List<String> errors = new ArrayList<String>();
        for (Diagnostic<? extends JavaFileObject> d : diagnostics.getDiagnostics()) {
            if (d.getKind() == Diagnostic.Kind.ERROR)
                errors.add("{\"line\":" + d.getLineNumber() + ",\"message\":" + json(d.getMessage(Locale.ROOT)) + "}");
        }
        System.out.println("{\"definitions\":[" + String.join(",", definitions) + "],\"references\":["
            + String.join(",", references) + "],\"errors\":[" + String.join(",", errors) + "]}");
    }
}
