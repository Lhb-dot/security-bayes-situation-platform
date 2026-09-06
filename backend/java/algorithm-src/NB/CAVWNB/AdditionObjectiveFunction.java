package weka.classifiers.zh.CAVWNB;

import weka.classifiers.zh.CAVWNB.WANBDistribution;
import weka.core.Instances;
import lbfgsb.FunctionValues;

public class AdditionObjectiveFunction extends BaseObjectiveFunction implements WANBObjectiveFunction  {
	WANBObjectiveFunction f1;
	WANBObjectiveFunction f2;
	public AdditionObjectiveFunction(WANBObjectiveFunction f1,WANBObjectiveFunction f2)
	{
		super(f1.getNumDimensions());
		//System.out.println("NumDimensions f1 = "+ f1.getNumDimensions() +"f2: "+ f2.getNumDimensions());
		assert f1.getNumDimensions()==f2.getNumDimensions();
		this.f1 = f1;
		this.f2 = f2;
	}
	
	@Override
	public void init(WANBDistribution distrib, Instances instances2) {
		f1.init(distrib, instances2);
		f2.init(distrib, instances2);
	}
	
	@Override
	public FunctionValues getValues(double[] w) {
		FunctionValues fv1 = f1.getValues(w);
		FunctionValues fv2 = f2.getValues(w);
		double g[] = new double[w.length];
		double f = fv1.functionValue + fv2.functionValue;
		for (int i = 0; i < w.length ; i++) {
			g[i] = fv1.gradient[i] + fv2.gradient[i];
		}
		return new FunctionValues(f, g);
	}

	@Override
	public int getNumDimensions() {
		return f1.getNumDimensions();
	}
}
