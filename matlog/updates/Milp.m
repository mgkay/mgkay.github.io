classdef Milp < handle
   %MILP Mixed-integer linear programming model.
   % This class stores MILP models and provides methods to create the models
   % and format solutions for output.
   % Milp Properties:
   %    Model        MILP model (same structure as Cplex model).
   % Milp Methods:
   %    Milp         Constructor for Milp objects.
   %    addobj       Add variable cost arrays to objective function.
   %    addcstr      Add constraint to model.
   %    addlb        Add lower bounds for each variable array.
   %    addub        Add upper bounds for each variable array.
   %    addctype     Specify type of each variable array.
   %    namesolution Convert solution to named field arrays.
   %    dispmodel    Display matrix view of model.
   %    lp2milp      Convert LP model to MILP model.
   %    milp2lp      Convert MILP model to LINPROG inputs.
   %    milp2ilp     Convert MILP model to INTLINPROG inputs.
   %    milp2gb      Convert MILP model to Gurobi input structure.
   %
   % Example 1: Illustrate Milp syntax
   %
   % c = [1:4], C = reshape(5:10,2,3)
   % mp = Milp('Example');
   % mp.addobj('min',c,C)
   %
   % mp.addcstr(0,1,'=',100)
   % mp.addcstr(c,-C,'>=',0)
   % mp.addcstr(c,'>=',C)
   % mp.addcstr([c; 2*c],repmat(C(:)',2,1),'<=',[400 500])
   % mp.addcstr({3},{2,2},'<=',600)
   % mp.addcstr({2,{3}},{3*3,{2,2}},'<=',700)
   % mp.addcstr({[2 3],{[3 4]}},{4,{2,':'}},'=',800)
   % mp.addcstr(0,{C(:,[2 3]),{':',[2 3]}},'>=',900)
   %
   % mp.addlb(-10,0)
   % mp.addub(10,Inf)
   % mp.addctype('B','C')
   % mp.dispmodel
   %
   % % c =  1     2     3     4
   % % C =
   % %      5     7     9
   % %      6     8    10
   % %
   % % Example:  lhs  B   B   B   B   C   C   C   C   C   C  rhs
   % % -------:-------------------------------------------------
   % %     Min:        1   2   3   4   5   6   7   8   9  10
   % %       1:  100   0   0   0   0   1   1   1   1   1   1 100
   % %       2:    0   1   2   3   4  -5  -6  -7  -8  -9 -10 Inf
   % %       3:    0   1   2   3   4  -5  -6  -7  -8  -9 -10 Inf
   % %       4: -Inf   1   2   3   4   5   6   7   8   9  10 400
   % %       5: -Inf   2   4   6   8   5   6   7   8   9  10 500
   % %       6: -Inf   0   0   1   0   0   0   0   1   0   0 600
   % %       7: -Inf   0   0   2   0   0   0   0   9   0   0 700
   % %       8:  800   0   0   2   3   0   4   0   4   0   4 800
   % %       9:  900   0   0   0   0   0   0   7   8   9  10 Inf
   % %      lb:      -10 -10 -10 -10   0   0   0   0   0   0
   % %      ub:       10  10  10  10 Inf Inf Inf Inf Inf Inf
   %
   % Example 2: UFL (Example 8.8 in Francis, Fac Layout and Loc, 2nd ed.)
   % k = [8     8    10     8     9     8];
   % C = [0     3     7    10     6     4
   %      3     0     4     7     6     7
   %      7     4     0     3     6     8
   %     10     7     3     0     7     8
   %      6     6     6     7     0     2
   %      4     7     8     8     2     0];
   % mp = Milp('UFL');
   % mp.addobj('min',k,C)
   % [n m] = size(C);
   % for j = 1:m
   %    mp.addcstr(0,{':',j},'=',1)
   % end
   % for i = 1:n
   %    mp.addcstr({m,{i}},'>=',{i,':'})  % Weak formulation
   % end
   % mp.addub(Inf,1)
   % mp.addctype('B','C')
   % [x,TC,nevals,XFlg] = milplog(mp); TC,nevals,XFlg
   % x = mp.namesolution(x), xC = x.C
   % TC = k*x.k' + sum(sum(C.*xC))

   
   % Copyright (c) 1994-2016 by Michael G. Kay
   % Matlog Version 17 06-Jan-2017 (http://www.ise.ncsu.edu/kay/matlog)
   
   properties
      % Model MILP model.
      %   Fields (same field names as in Cplex model):
      %     name     Name of model ('Milp', default).
      %     sense    String indicating whether min or max problem.
      %     obj      Row vector of objective function costs.
      %     lb       Row vector of variable lower bounds (0,default).
      %     ub       Row vector of variable upper bounds (Inf, default).
      %     ctype    Row character vector of variable types ('C', default).
      %     A        Constraint matrix.
      %     lhs      Column vector of constrint lefthand side values.
      %     rhs      Column vector of constrint righthand side values.
      Model = cell2struct(cell(9,1),...
         {'name','sense','obj','lb','ub','ctype','A','lhs','rhs'},1);
   end
   properties (Access = 'private')
      insiz;
      inname;
      idxA = [];   % Index of last real constraint (used in trimcstr)
      isAtrans;
   end
   events
   end
   methods
      function obj = Milp(name)
         % Milp Constructor for Milp objects.
         if nargin == 0
            name = 'Milp';
         end
         obj.Model.name = name;
      end
      function addobj(obj,varargin)
         % addobj Add variable cost arrays to objective function.
         %    C(2x3), D(3x4x2) -> addobj(C,D) -> obj(2x3 + 3x4x2)
         sense = varargin{1}(:)';
         idx  = find(strcmpi(sense,{'minimize','min','maximize','max'}));
         if ~ischar(sense) || isempty(idx)
            error('Incorrect model sense first input argument.')
         end
         if idx < 3
            obj.Model.sense = 'minimize';
         else
            obj.Model.sense = 'maximize';
         end
         obj.insiz = cellfun(@size,varargin(2:end),'UniformOutput',false);
         n = cellfun(@prod,obj.insiz);
         obj.Model.obj = [];
         for i = 2:length(varargin)
            c = varargin{i}(1:n(i-1));
            obj.Model.obj = [obj.Model.obj c(:)'];
            if isempty(inputname(i+1))
               obj.inname{i-1} = ['arg' num2str(i-1)];
            else
               obj.inname{i-1} = inputname(i+1);
            end
         end       % Add sqrt(eps) to make all non-zero objective
         % coefficient values to make Cplex work correctly
         obj.Model.obj(obj.Model.obj == 0) = sqrt(eps);
         obj.Model.lb = zeros(1,sum(n));
         obj.Model.ub = inf(1,sum(n));
         obj.Model.ctype = repmat('C',1,sum(n));
         obj.Model.A = sparse(sum(n),0);
         obj.idxA = 0;
         obj.isAtrans = true;
      end
      function addlb(obj,varargin)
         % addlb Add lower bounds for each variable array.
         obj.Model.lb = add(obj,varargin{:});
         if any(obj.Model.lb > obj.Model.ub)
            error('Variable lower bound exceeds upper bound.')
         elseif any(obj.Model.lb(obj.Model.ctype == 'B') > 0)
            error('Variable lower bound not compatible with binary type.')
         end
         obj.trimcstr
      end
      function addub(obj,varargin)
         % addub Add upper bounds for each variable array.
         obj.Model.ub = add(obj,varargin{:});
         if any(obj.Model.lb > obj.Model.ub)
            error('Variable upper bound less than lower bound.')
         elseif any(obj.Model.ub(obj.Model.ctype == 'B') < 1)
            error('Variable upper bound not compatible with binary type.')
         end
         obj.trimcstr
      end
      function addctype(obj,varargin)
         % addctype Specify type of each variable array.
         %   Valid character type values are:
         %      'B' Binary
         %      'I' General integer
         %      'C' Continuous
         %      'S' Semi-continous
         %      'N' Semi-integer
         if any(cellfun(@isempty,regexp(varargin(:)','[BICSN]')))
            error('Characters in ctype must be belong to BICSN')
         end
         obj.Model.ctype = add(obj,varargin{:});
%          if any(obj.Model.lb(obj.Model.ctype == 'B') > 0) || ...
%                any(obj.Model.ub(obj.Model.ctype == 'B') < 1)
%             error('Variable bounds not compatible with binary type.')
%          end
         obj.trimcstr
      end
      function addcstr(obj,varargin)
         % addcstr Add constraint to model.
         %   Use '<=', '=', or '>=' to specify less-than, equality, or
         %   greater-than constraint types, respectively.
         if isempty(obj.insiz)
            error('Must call "addobj" first.')
         end
         isAtrans = obj.isAtrans;
         if ~isAtrans  % make A transpose for just this call (needed if
            % addcstr called after trimcstr called)
            obj.Model.A = obj.Model.A';
         end
         n = cellfun(@prod,obj.insiz);
         idxct = find(cellfun(@ischar,varargin));
         if isempty(idxct)
            error('Must specify constraint-type string for constraint.')
         end
         cstrtype = varargin{idxct(1)}(:)';
         if length(idxct) ~= 1
            error('Only one contraint-type string allowed.')
         elseif ~any(strcmp(cstrtype,{'<=','=','>='}))
            error('Constraint type must be >=, =, or <=')
         elseif idxct < 2 || idxct > length(varargin) - 1
            error('Constraint type cannot be first or last argument.')
         end
         varargin(idxct) = [];
         if length(varargin) < length(n) || ...
               length(varargin) > length(n) + 1
            error('Incorrect number of constraint arguments.')
         end
         isminus = false(1,length(n));
         if length(varargin) == length(n)
            b = 0;
            isminus(idxct:end) = true;
         else
            if idxct < length(varargin)
               error('Constraint type not next-to-last input argument.')
            end
            b = varargin{end}(:);
            varargin(end) = [];
         end
         p = 1;
         for j = 1:length(varargin)
            [v{j},i{j},p] = obj.getvip(obj.insiz{j},varargin{j},p);
            if isminus(j), v{j} = -v{j}; end
         end
         if isscalar(b), b = repmat(b,p,1); end
         if ~isreal(b) || length(b) ~= p
            error('Incorrect right-hand-side.')
         end
         a = sparse([]);
         for j = 1:length(varargin)
            if ~isempty(i{j})
               linidx = obj.getlinidx(obj.insiz{j},i{j});
               norep = length(linidx)/length(v{j});
               % If includes sum over variable (':') then replicate
               % coefficients norep times to match length of linidx
               if norep ~= 1 && mod(length(linidx),length(v{j})) == 0
                  v{j} = repmat(v{j},1,norep);
               end
               if length(v{j}) == 1 || length(linidx) == length(v{j})
                  vj = sparse(linidx,1,v{j},prod(obj.insiz{j}),1);
               elseif length(v{j}) == prod(obj.insiz{j})
                  vj = sparse(linidx,1,v{j}(linidx),prod(obj.insiz{j}),1);
               else
                  error('Incorrect dimention of constraint index.')
               end
            else
               if length(v{j}) == 1
                  vj = repmat(v{j},prod(obj.insiz{j}),p);
               else
                  vj = v{j}';
               end
            end
            if isempty(a) || isequal(size(a,2),size(vj,2))
               a = [a; vj];
            else
               error('Incorrect number of rows in constraint array.')
            end
         end
         if obj.idxA + size(a,2) > size(obj.Model.A,2)
            nzmax = min(sum(n)*sum(n),max(1e6,5*sum(n)));
            obj.Model.A = ...
               cat(2,obj.Model.A,spalloc(sum(n),sum(n),nzmax));
            obj.Model.lhs = cat(1,obj.Model.lhs,-Inf(sum(n),1));
            obj.Model.rhs = cat(1,obj.Model.rhs,Inf(sum(n),1));
         end
         idxa = obj.idxA+1:obj.idxA+size(a,2);
         obj.Model.A(:,idxa) = a;
         if strcmp(cstrtype,'<=')
            obj.Model.lhs(idxa) = -Inf(size(b));
            obj.Model.rhs(idxa) = b;
         elseif strcmp(cstrtype,'>=')
            obj.Model.lhs(idxa) = b;
            obj.Model.rhs(idxa) = Inf(size(b));
         else
            obj.Model.lhs(idxa) = b;
            obj.Model.rhs(idxa) = b;
         end
         obj.idxA = obj.idxA + size(a,2);
         if ~isAtrans  % restore A after just this call (needed if
            % addcstr called after trimcstr called)
            obj.Model.A = obj.Model.A';
         end
      end
      function trimcstr(obj)
         % trimcstr Remove empty constraints from model.
         %    A, lhs, and rhs initialized with empty constraints in order
         %    to improve speed. Since trimcstr called by all methods except
         %    Milp, addobj, addcstr, and lp2milp, it only needs to be
         %    called if addcstr is the last method executed.
         if isempty(obj.idxA), return, end   % no need, addobj not called
         if obj.isAtrans                    
            obj.Model.A = obj.Model.A';
            obj.isAtrans = false;
         end
         obj.Model.A = obj.Model.A(1:obj.idxA,:);
         obj.Model.lhs = obj.Model.lhs(1:obj.idxA);
         obj.Model.rhs = obj.Model.rhs(1:obj.idxA);
      end
      function xout = namesolution(obj,x)
         % namesolution Convert solution to named field arrays.
         %    Each named field has same size as corresponding variable
         %    array in objective function.
         if isempty(obj.insiz)
            error('Must call "addobj" first.')
         end
         n = cumsum([0 cellfun(@prod,obj.insiz)]);
         x = x(:);
         if ~isreal(x) || length(x) ~= n(end)
            error('Incorrect solution input.')
         end
         for i = 1:length(n)-1
            xout.(obj.inname{i}) = reshape(x(n(i)+1:n(i+1)),obj.insiz{i});
         end
         obj.trimcstr
      end
      function str = dispmodel(obj)
         % dispmodel Display matrix view of model.
         % str = dispmodel, optional output to "str" without horizontal
         %                  and vertical separators
         % Note: uses MDISP for display
         if strcmp(obj.Model.sense,'minimize')
            sense = 'Min';
         else
            sense = 'Max';
         end
         obj.trimcstr
         ctype = cellstr(obj.Model.ctype')';
         if ~isempty(obj.Model.A)
            M = [NaN obj.Model.obj NaN];
            M = [M; obj.Model.lhs obj.Model.A obj.Model.rhs];
            M = [M; [NaN obj.Model.lb NaN]; [NaN obj.Model.ub NaN]];
            col = {'lhs',ctype{:},'rhs'};
            cstrnum = cellstr(num2str((1:size(obj.Model.A,1))'));
            row = {sense,cstrnum{:},'lb','ub'};
         else
            M = [NaN obj.Model.obj];
            M = [M; [NaN obj.Model.lb]; [NaN obj.Model.ub]];
            col = {' ',ctype{:}};
            row = {sense,'lb','ub'};
         end
         if nargout > 0
            str = mdisp(M,row,col,obj.Model.name,[],[],[],1);
         else
            mdisp(M,row,col,obj.Model.name,[],[],[],1)
         end
      end
      function lp2milp(obj,c,Alt,blt,Aeq,beq,lb,ub)
         % lp2milp Convert LP model to MILP model.
         %   milp.lp2milp(c,Alt,blt,Aeq,beq,lb,ub)
         %     c = vector of variable costs
         %   Alt = inequality constraint matrix
         %   blt = inequality RHS vector
         %   Aeq = equality constraint matrix
         %   beq = equality RHS vector
         %    lb = lower bound vector
         %    ub = upper bound vector
         obj.Model.sense = 'minimize';
         obj.Model.obj = c(:)';
         obj.insiz = {size(obj.Model.obj')};  % Since not calling addobj
         obj.inname = {'c'};
         obj.Model.lb = lb(:)';
         obj.Model.ub = ub(:)';
         obj.Model.ctype = repmat('C',1,length(c(:)));
         obj.Model.A = [Alt; Aeq];
         obj.Model.lhs = [-inf(size(Alt,1),1); beq(:)];
         obj.Model.rhs = [blt(:); beq(:)];
      end
      function lp = milp2lp(obj)
         % milp2lp Convert MILP model to LP model.
         %  lp = milp.milp2lp
         %    lp = {c,Alt,blt,Aeq,beq,lb,ub};
         %     c = vector of variable costs
         %   Alt = inequality constraint matrix
         %   blt = inequality RHS vector
         %   Aeq = equality constraint matrix
         %   beq = equality RHS vector
         %    lb = lower bound vector
         %    ub = upper bound vector
         if isempty(obj.insiz)
            error('Must call "addobj" first.')
         end
         obj.trimcstr
         c = obj.Model.obj';
         if ~strcmp(obj.Model.sense,'minimize'), c = -c; end
         lb = obj.Model.lb';
         ub = obj.Model.ub';
         iseq = obj.Model.lhs == obj.Model.rhs;
         isgt = isinf(obj.Model.rhs) & ~iseq;
         islt = ~isgt & ~iseq;
         Alt = [obj.Model.A(islt,:); -obj.Model.A(isgt,:)];
         blt = [obj.Model.rhs(islt); -obj.Model.lhs(isgt)];
         Aeq = obj.Model.A(iseq,:);
         beq = obj.Model.rhs(iseq);
         lp = {c,Alt,blt,Aeq,beq,lb,ub};
      end
      function ilp = milp2ilp(obj)
         % milp2ilp Convert MILP model to INTLINPROG inputs.
         % ilp = milp.milp2ilp
         %    ilp = {c,intcon,Alt,blt,Aeq,beq,lb,ub};
         %      c = vector of variable costs
         % intcon = integer varible indices
         %    Alt = inequality constraint matrix
         %    blt = inequality RHS vector
         %    Aeq = equality constraint matrix
         %    beq = equality RHS vector
         %     lb = lower bound vector
         %     ub = upper bound vector
         %
         % Note: for milp.Model.ctype = 'B', lb set = 0 and ub set = 1
         ilp = obj.milp2lp;
         isB = 'B' == obj.Model.ctype;
         ilp = {ilp{1},find(isB | 'I' == obj.Model.ctype),ilp{2:end}};
         ilp{end-1}(isB) = 0;
         ilp{end}(isB) = 1;
      end
      function model = milp2gb(obj)
         % milp2gb Convert MILP model to Gurobi model.
         %  model = milp.milp2gb
         %        = struct that contains fields:
         %       .name - model name string
         % .modelsense - 'min', 'max'
         %        .obj - objective function coefficient vector
         %         .lb - lower bound vector
         %         .ub - upper bound vector
         %          .A - constraint matrix (must be a sparse matrix)
         %      .sense - char array of '<','>','='
         %        .rhs - b vector 
         %      .vtype - char array of variable type: 'B','I','C','S','N'
         %
         % Thanks to Karthick Gopalswamy for his help with the using of
         % Gurobi and Matlab
         if isempty(obj.insiz)
            error('Must call "addobj" first.')
         end
         model.name = obj.Model.name;
         model.modelsense = obj.Model.sense;
         model.obj = obj.Model.obj';
         model.lb = obj.Model.lb';
         model.ub = obj.Model.ub';
         model.vtype = obj.Model.ctype;
         iseq = obj.Model.lhs == obj.Model.rhs;
         isgt = isinf(obj.Model.rhs) & ~iseq;
         islt = ~isgt & ~iseq;
         model.A = [obj.Model.A(islt,:); obj.Model.A(isgt,:); ...
            obj.Model.A(iseq,:)];
         model.sense = [repmat('<',nnz(islt),1); ...
            repmat('>',nnz(isgt),1); ...
            repmat('=',nnz(iseq),1)];
         model.rhs = [obj.Model.rhs(islt); obj.Model.lhs(isgt); ...
            obj.Model.rhs(iseq)];
      end
   end
   methods (Access = 'private')
      function x = add(obj,varargin)
         if isempty(obj.insiz)
            error('Must call "addobj" first.')
         end
         n = cellfun(@prod,obj.insiz);
         if length(varargin) == 1 && length(varargin{1}(:)) == 1
            x = repmat(varargin{1}(1),1,sum(n));
         elseif length(varargin) == length(n)
            x = [];
            for i = 1:length(varargin)
               if length(varargin{i}(:)) == 1
                  x = [x repmat(varargin{i}(1),1,n(i))];
               elseif numel(varargin{i}) == n(i)
                  x = [x varargin{i}(1:n(i))];
               else
                  error(['Size of input argments must be scalar or ',...
                     'equal to corresponding array in objective.'])
               end
            end
         else
            error('Unequal number of input argments and objective arrays.')
         end
      end
   end
   methods (Access = 'private', Static = true)
      function [v,i,p] = getvip(siz,vi,p)
         if isreal(vi)
            v = vi;
            i = [];
         elseif iscell(vi)
            if length(vi) == 2 && isreal(vi{1}) && iscell(vi{2})
               v = vi{1};
               i = vi{2};
            else
               v = 1;
               i = vi;
            end
         else
            error('Constraint argument not real matrix or cell array.')
         end
         if isreal(v) && numel(v) <= prod(siz) && ...
               (size(v,1) == p || p == 1 || isscalar(v))
            v = v(:)';
         elseif isreal(v) && size(v,2) == prod(siz) && ...
               (size(v,1) == p || p == 1)
            p = size(v,1);
         else
            error('Size of constraint-value real matrix incorrect.')
         end
      end
      function linidx = getlinidx(siz,idx)
         if length(siz) == 2 && min(siz) == 1, siz = sort(siz); end
         if length(idx) == 1, idx = {1,idx{1}}; end
         if length(siz) ~=  length(idx)
            error('Incorrect dimention of constraint index.')
         end
         for i = 1:length(idx)
            if strcmp(':',idx{i}), idx{i} = 1:siz(i); end
         end
         m = cellfun(@length,idx);
         if length(m) < 3 && ~all(m == max(m) | m == 1)
            error('Incorrect dimention of constraint index.')
         end
         is = m == 1;
         if all(is)
            linidx = sub2ind(siz,idx{:});
         elseif sum(is) == length(is) - 1
            for i = find(is)
               idx{i} = repmat(idx{i},1,m(~is));
            end
            linidx = sub2ind(siz,idx{:});
         else
            for i = 1:length(idx)
               if length(idx{i}) == 1
                  idx{i} = repmat(idx{i},1,max(m));
               end
            end
            [IDX{1:length(idx)}] = ndgrid(idx{:});
            linidx = sub2ind(siz,IDX{:});
            linidx = unique(linidx(:)');
         end
      end
   end
end
