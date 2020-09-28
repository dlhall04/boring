from scipy.integrate import odeint
import matplotlib.pyplot as plt
import numpy as np
import openmdao.api as om
from openmdao.utils.assert_utils import assert_check_partials

import dymos as dm
from dymos.examples.plotting import plot_results


class tempODE(om.ExplicitComponent):
    """Calculate the temperature rise between cells with heat flux across the insulation thickness
    """
    def initialize(self):
        self.options.declare('num_nodes', types=int)

    def setup(self):
        nn = self.options['num_nodes']

        # Inputs
        self.add_input('K', val=0.03*np.ones(nn), desc='insulation conductivity', units='W/m*K')
        self.add_input('A', val=.102*.0003*np.ones(nn), desc='area', units='m**2')
        self.add_input('d', val=0.03*np.ones(nn), desc='insulation thickness', units='m')
        self.add_input('m', val=0.06*np.ones(nn), desc='cell mass', units='kg')
        self.add_input('Cp', val=3.56*np.ones(nn), desc='specific heat capacity', units='kJ/kg*K')
        self.add_input('Th', val=773.*np.ones(nn), desc='hot side temp', units='K')
        self.add_input('T', val=373.*np.ones(nn), desc='cold side temp', units='K')

        # Outputs
        self.add_output('Tdot', val=np.zeros(nn), desc='temp rate of change', units='K/s')

        # Setup partials
        arange = np.arange(self.options['num_nodes'])
        c = np.zeros(self.options['num_nodes'])
        self.declare_partials(of='Tdot', wrt='K', rows=arange, cols=arange) 
        self.declare_partials(of='Tdot', wrt='A', rows=arange, cols=arange) 
        self.declare_partials(of='Tdot', wrt='m', rows=arange, cols=arange) 
        self.declare_partials(of='Tdot', wrt='Cp', rows=arange, cols=arange) 
        self.declare_partials(of='Tdot', wrt='Th', rows=arange, cols=arange) 
        self.declare_partials(of='Tdot', wrt='d', rows=arange, cols=arange)
        self.declare_partials(of='Tdot', wrt='T', rows=arange, cols=arange)
        #self.declare_partials(of='*', wrt='*', method='cs') # use this if you don't provide derivatives

    def compute(self, i, o):

        dT_num = i['K']*i['A']*(i['Th']-i['T'])/i['d']
        dT_denom = i['m']*i['Cp']
        o['Tdot'] = dT_num/dT_denom

    def compute_partials(self, i, partials):
    
        partials['Tdot','T'] = -i['K']*i['A']/(i['d']*i['m']*i['Cp'])
        partials['Tdot','K']  = i['A']*(i['Th']-i['T'])/(i['d']*i['m']*i['Cp'])
        partials['Tdot','A']  = i['K']*(i['Th']-i['T'])/(i['d']*i['m']*i['Cp'])
        partials['Tdot','Th'] = i['K']*i['A']/(i['d']*i['m']*i['Cp'])
        partials['Tdot','d']  = -i['K']*i['A']*(i['Th']-i['T'])/(i['m']*i['Cp']*i['d']**2)
        partials['Tdot','m']  = -i['K']*i['A']*(i['Th']-i['T'])/(i['d']*i['Cp']*i['m']**2)
        partials['Tdot','Cp'] = -i['K']*i['A']*(i['Th']-i['T'])/(i['d']*i['m']*i['Cp']**2)


'''
Use Dymos to minimize the thickness of the insulator,
while still maintaining a temperature below 100degC after a 45 second transient
'''

p = om.Problem(model=om.Group())
p.driver = om.ScipyOptimizeDriver()
p.driver = om.pyOptSparseDriver(optimizer='SLSQP')
# p.driver.opt_settings['iSumm'] = 6
p.driver.declare_coloring()

traj = p.model.add_subsystem('traj', dm.Trajectory())

phase = traj.add_phase('phase0',
                       dm.Phase(ode_class=tempODE,
                                transcription=dm.GaussLobatto(num_segments=20, order=3, compressed=False)))

phase.set_time_options(fix_initial=True, fix_duration=True)

phase.add_state('T', rate_source='Tdot', units='K', ref=333.15, defect_ref=333.15,
                fix_initial=True, fix_final=False, solve_segments=False)


phase.add_boundary_constraint('T', loc='final', units='K', upper=333.15, lower=293.15, shape=(1,))
phase.add_parameter('d', opt=True, lower=0.001, upper=0.5, val=0.001, units='m', ref0=0, ref=1)
phase.add_objective('d', loc='final', ref=1)
p.model.linear_solver = om.DirectSolver()
p.setup()
p['traj.phase0.t_initial'] = 0.0
p['traj.phase0.t_duration'] = 45
p['traj.phase0.states:T'] = phase.interpolate(ys=[293.15, 333.15], nodes='state_input')
p['traj.phase0.parameters:d'] = 0.001

p.run_model()
# cpd = p.check_partials(method='cs', compact_print=True) #check partial derivatives
# assert_check_partials(cpd)
# quit()

dm.run_problem(p)

print(p['traj.phase0.parameters:d'])

exp_out = traj.simulate() # this is equivalent to the scipy odeint function, with some extra features
plot_results([('traj.phase0.timeseries.time', 'traj.phase0.timeseries.states:T','time (s)','temp (K)')],
             title='Temps', p_sol=p, p_sim=exp_out)
plt.show()





# Vanilla python approach to the ODE integration, no optimization
# t = np.linspace(0, 45, 101)


# def dT_calc(Ts,t):

#     Tf = Ts[0]
#     Tc = Ts[1]
#     K = 0.03 # W/mk
#     A = .102*.0003 # m^2
#     d = 0.003 #m
#     m = 0.06 #kg
#     Cp = 3.58 #kJ/kgK

#     dT_num = K*A*(Tf-Tc)/d
#     dT_denom = m*Cp

#     return [0, (dT_num/dT_denom)]


# y0 = [900, 20]
# sol = odeint(dT_calc, y0, t)

# print(sol[100,1])


# #plt.plot(t, sol[:, 0], 'b', label='hot')
# plt.plot(t, sol[:, 1], 'g', label='cold')
# plt.legend(loc='best')
# plt.xlabel('t')
# plt.grid()
# plt.show()