% Matlab M-file to add Matlog toolbox to path list
if isunix
   path(path,'/afs/eos/lockers/research/ie/kay/matlog');
   path(path,'/afs/eos/courses/ise/ise754/common/matlab754');
else
   path(path,'j:/eos/lockers/research/ie/kay/matlog');
   path(path,'j:/eos/courses/ise/ise754/common/matlab754');
end
format compact
