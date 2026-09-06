package weka.classifiers.zh.CAVWNB;

import java.util.ArrayList;
import java.util.List;

import lbfgsb.Bound;
import lbfgsb.DifferentiableFunction;
import lbfgsb.LBFGSBException;
import lbfgsb.Minimizer;
import lbfgsb.Result;
import lbfgsb.StopConditions;

import weka.classifiers.zh.CAVWNB.WANBDistribution;
import weka.core.Instances;

public  class BaseWeightComputer implements WeightComputer {
	protected double weights[];
	
	protected WANBObjectiveFunction f;
	
	protected List<Bound> createBounds() {
		ArrayList<Bound> bounds = new ArrayList<Bound>();
		for (int u = 0 ; u < weights.length ; u++) {
			bounds.add(new Bound(new Double(0), new Double(1)));
		}
		return bounds;
	}
	
	@Override
	public double[] assessWeights(WANBDistribution distrib,Instances instances) {
		f.init(distrib,instances);
		weights = distrib.getWeights();
		
		Minimizer alg = new Minimizer();
		StopConditions sc = alg.getStopConditions();
		//System.out.println("Stop conditions");
		//System.out.println("FRF = "+sc.getFunctionReductionFactor());
		sc.setMaxGradientNorm(0.000000000000000000000000000000001);
		//System.out.println("MGN = "+sc.getMaxGradientNorm());
		//System.out.println("MI = "+sc.getMaxIterations());
		alg.setBounds(createBounds());
		return optimize(alg,f);
	}
	
	

	protected double[] optimize(Minimizer alg,DifferentiableFunction sp){
		try {
			Result result = alg.run(sp, weights);
			//System.out.println("The final result: "+result);
			return result.point;
		} catch(LBFGSBException e) {
			e.printStackTrace();
			return null;
		}
	}
	
	public void setObjectiveFunction(WANBObjectiveFunction f) {
		this.f = f;
	}
//	
//	protected double[] optimize(Minimizer alg,DifferentiableFunction sp){
//		int RUNS = 100;
//		double sols[][] = new double[RUNS][weights.length];
//		double starting_point[] = new double[weights.length];
//		Result result = null;
//		for (int i = 0; i < 100 ; i++) {
//			for (int j = 0 ; j < weights.length ; j++) {
//				starting_point[j] = Math.random();
//			}
//			try {
//				result = alg.run(sp, starting_point);
//				System.out.println("Starting at: "+Arrays.toString(starting_point));
//				System.out.println("The final result is : "+result);
//				System.arraycopy(result.point,0,sols[i],0,weights.length);
//			} catch(LBFGSBException e) {
//				e.printStackTrace();
//				return null;
//			}
//		}
//		return result.point;
//	}
}
