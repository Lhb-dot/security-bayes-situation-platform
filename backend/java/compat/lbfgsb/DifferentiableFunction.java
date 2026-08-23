package lbfgsb;

public interface DifferentiableFunction {
    FunctionValues getValues(double[] point);
}
