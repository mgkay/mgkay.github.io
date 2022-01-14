function TC = myrteTC(rte,rTDh0,maxdist)
% My VRP constraints
TC = rTDh0(rte);
if TC > maxdist
   TC = Inf;
end
