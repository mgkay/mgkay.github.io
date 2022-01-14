%% Network Models 3: Production Planning

%% Single Product Example - 2-stage, 6-month
%% Input data
K = [50  0 50  0  0 50;    % capacity of stage m in period t (ton)
     60  0  0 60 60 60];
D = [20 10 15 20 15 25]';  % demand in period t (ton)
Cp = [200; 800];           % production cost in stage m ($/ton)
h = 0.3/12
Ci = cumsum(Cp)*h          % inventory cost for stage m ($/ton)
yinit = [0; 0];            % initial inventory of stage m (ton)
yfinal = yinit;            % final inventory of stage m (ton)
M = size(K,1);             % number of production stages = 2
T = size(D,1);             % number of periods of production = 6
%% Create MILP model
Cp = repmat(Cp,1,T)
Ci = repmat(Ci,1,T+1)
Ci(:,1) = 0  % Intital inventory cost already accounted for last period 
mp = Milp('PPlan');
mp.addobj('min',Cp,Ci)  % Objective
for t = 1:T  % Flow balance constraints
   for m = 1:M-1
      mp.addcstr({[1 -1],{[m m+1],t}},{[1 -1],{m,[t t+1]}},'=',0)
   end
   mp.addcstr({M,t},{[1 -1],{M,[t t+1]}},'=',D(t))
end
mp.addlb(0,[yinit zeros(M,T-1) yfinal])  % Lower bounds
mp.addub(K,[yinit inf(M,T-1) yfinal])    % Upper bounds
% default 'C' so mp.ctype('C','C') not needed 
%% Display model
mp.dispmodel
%% Solve using LINPROG (LP, since no discrete variables)
lp = mp.milp2lp;
[x,TC,exitflag,output] = linprog(lp{:});
TC, output
x = mp.namesolution(x)
%% Solve using Gurobi
clear params
model = mp.milp2gb
params.outputflag = 1;
result = gurobi(model, params);
x = mp.namesolution(result.x)
TC = result.objval
%% Report results
Fp = x.Cp; mdisp(Fp)
Fi = x.Ci; mdisp(Fi)
mdisp(D)

%% Multiple Product Example - 2-product, 3-stage, 6-month
%% Input data
K = [50 35;               % capacity for product g in stage m (ton)
     60 45;
     70 55];
D = [20 10 15 20 15 25;   % demand for product g in period t (ton)
     10 15 25 10  5 15]';

Cp = [100  200;           % production cost of product g at stage m ($/ton)
      800 1200;
      400  800];
h = 0.3/12
Ci = cumsum(Cp,1)*h      % inventory cost of product g for stage m ($/ton)

Cs = [2800 3200;         % stage-m product-g setup cost ($)
       800  600;
       400  300];
yinit = [0  0;           % initial product g inventory at stage m (ton)
         0  0;
         0 25];
yfinal = zeros(3,2);     % final product g inventory at stage m (ton)
k0 = [1 0;               % initial setup at stage m for product g
      1 0;
      1 0];
M = size(K,1);           % number of production stages = 3
T = size(D,1);           % number of periods of production = 6
G = size(K,2);           % number of products produced = 2
%% Create MILP model
Cp = reshape(repmat(Cp,[T 1 1]),M,T,G)     % create M x T x G array (3-D)
Ci = reshape(repmat(Ci,[T+1 1 1]),M,T+1,G) % create M x (T+1) x G array
Ci(:,1,:) = 0   % intital inventory cost already accounted for last period
Cs = reshape(repmat(Cs,[T 1 1]),M,T,G)     % create M x T x G array
mp = Milp('PPlan');
mp.addobj('min',Cp,Ci,Cs,zeros(M,T,G))     % zeros(M,T,G) dummy array for k
for g = 1:G
   for t = 1:T
      for m = 1:M-1
         mp.addcstr({[1 -1],{[m m+1],t,g}},{[1 -1],{m,[t t+1],g}},0,0,'=',0)
      end
      mp.addcstr({M,t,g},{[1 -1],{M,[t t+1],g}},0,0,'=',D(t,g))
      for m = 1:M
         mp.addcstr({m,t,g},0,0,'<=',{K(m,g),{m,t,g}})
      end
   end
   for m = 1:M
      mp.addcstr(0,0,{-1,{m,1,g}},{m,1,g},'<=',k0(m,g))
      for t = 2:T
         mp.addcstr(0,0,{-1,{m,t,g}},{[1 -1],{m,[t t-1],g}},'<=',0)
      end
   end
end
for m = 1:M, for t = 1:T, mp.addcstr(0,0,0,{m,t,':'},'=',1), end, end
mp.addlb(0,horzcat(reshape(yinit,M,1,G),zeros(M,T-1,G),reshape(yfinal,M,1,G)),0,0)
mp.addub(Inf,horzcat(reshape(yinit,M,1,G),inf(M,T-1,G),reshape(yfinal,M,1,G)),1,1)
mp.addctype('C','C','B','B')
%% Display contraint matrix
spy(mp.Model.A),shg
%% Solve using INTLINPROG (k,z are binary variables)
ilp = mp.milp2ilp;
[x,TC,exitflag,output] = intlinprog(ilp{:});
TC,output
x = mp.namesolution(x)
%% Solve using Gurobi
clear params
model = mp.milp2gb
params.outputflag = 1;
result = gurobi(model, params);
x = mp.namesolution(result.x)
TC = result.objval
%% Report results
Fp = x.Cp;
Fi = x.Ci;
Fs = x.Cs;
Fk = x.arg4;
for g = 1:G
   mdisp(D(:,g)',[],[],['D' num2str(g)])
   mdisp(Fp(:,:,g),[],[],['Fp' num2str(g)])
   mdisp(Fi(:,:,g),[],[],['Fi' num2str(g)])
   mdisp(Fs(:,:,g),[],[],['Fs' num2str(g)])
   mdisp(Fk(:,:,g),[],[],['Fk' num2str(g)])
end
