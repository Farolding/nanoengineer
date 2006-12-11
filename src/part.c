/* Copyright (c) 2006 Nanorex, Inc. All rights reserved. */

#include "simulator.h"

#define CHECK_VALID_BOND(b) { \
    NULLPTR(b); NULLPTR((b)->a1); NULLPTR((b)->a2); }

static char const rcsid[] = "$Id$";

// This is the default value for the p->parseError() function.
// p->parseError() is called by routines in this file while a part is
// being constructed.  It generally points to a routine that can emit
// line number and character position information to identify the
// location of the error in the input file.  The stream pointer is
// used to pass that information through to the parser's parseError
// routine.
//
// If the parser does not declare a parseError routine, or after
// endPart() is called to indicate that the parser is no longer
// responsible for errors, this routine will be installed as
// p->parseError().  When that happens, the stream pointer is set to
// the part, allowing us to extract and print the filename where the
// problem was found.
static void
defaultParseError(void *stream)
{
    struct part *p;
    
    p = (struct part *)stream;
    ERROR1("Parsing part %s", p->filename);
    done("Failed to parse part %s", p->filename);
    exit(1); // XXX should throw exception so pyrex doesn't exit cad here
}

// Create a new part.  Pass in a filename (or any other string
// identifying where the data for this part is coming from), and an
// error handler.  The parseError() routine will be called with stream
// as it's only argument if any of the routines in this file detect an
// error before you call endPart().  Pass NULL for both parseError and
// stream to use a default error handler.  The default error handler
// will also be used after a call to endPart() if an error is
// detected.
struct part *
makePart(char *filename, void (*parseError)(void *), void *stream)
{
    struct part *p;
    
    p = (struct part *)allocate(sizeof(struct part));
    memset(p, 0, sizeof(struct part));
    p->max_atom_id = -1;
    p->filename = copy_string(filename);
    p->parseError = parseError ? parseError : &defaultParseError;
    p->stream = parseError ? stream : p;
    return p;
}

void
destroyPart(struct part *p)
{
    int i;
    int k;
    struct atom *a;
    struct bond *b;
    struct jig *j;
    struct vanDerWaals *v;
    struct rigidBody *rb;
    
    if (p == NULL){
        return;
    }
    if (p->filename != NULL) {
        free(p->filename);
        p->filename = NULL;
    }
    // p->stream is handled by caller.  readmmp just keeps the stream
    // in it's stack frame.
    destroyAccumulator(p->atom_id_to_index_plus_one);
    p->atom_id_to_index_plus_one = NULL;
    for (i=0; i<p->num_atoms; i++) {
        a = p->atoms[i];

        //a->type points into periodicTable, don't free
        //a->prev and next just point to other atoms
        //a->bonds has pointers into the p->bonds array
        free(a->bonds);
        a->bonds = NULL;
        free(a);
    }
    destroyAccumulator(p->atoms);
    p->atoms = NULL;
    destroyAccumulator(p->positions);
    p->positions = NULL;
    destroyAccumulator(p->velocities);
    p->velocities = NULL;

    for (i=0; i<p->num_bonds; i++) {
        b = p->bonds[i];
        // b->a1 and a2 point to already freed atoms
        free(b);
    }
    destroyAccumulator(p->bonds);
    p->bonds = NULL;

    for (i=0; i<p->num_jigs; i++) {
        j = p->jigs[i];
        if (j->name != NULL) {
            free(j->name);
            j->name = NULL;
        }
        free(j->atoms);
        j->atoms = NULL;
        if (j->type == RotaryMotor) {
            if (j->j.rmotor.u != NULL) {
                free(j->j.rmotor.u);
                free(j->j.rmotor.v);
                free(j->j.rmotor.w);
                free(j->j.rmotor.rPrevious);
                j->j.rmotor.u = NULL;
                j->j.rmotor.v = NULL;
                j->j.rmotor.w = NULL;
                j->j.rmotor.rPrevious = NULL;
            }
        }
        free(j);
    }
    destroyAccumulator(p->jigs);
    p->jigs = NULL;

    if (p->rigid_body_info != NULL) {
        rigid_destroy(p);
        p->rigid_body_info = NULL;
    }
    for (i=0; i<p->num_rigidBodies; i++) {
        rb = &p->rigidBodies[i];
        free(rb->name);
        rb->name = NULL;
        destroyAccumulator(rb->stations);
        rb->stations = NULL;
        for (k=0; k<rb->num_stations; k++) {
            free(rb->stationNames[k]);
        }
        destroyAccumulator(rb->stationNames);
        rb->stationNames = NULL;
        destroyAccumulator(rb->axies);
        rb->axies = NULL;
        for (k=0; k<rb->num_axies; k++) {
            free(rb->axisNames[k]);
        }
        destroyAccumulator(rb->axisNames);
        rb->axisNames = NULL;
        for (k=0; k<rb->num_joints; k++) {
            ;
        }
        destroyAccumulator(rb->joints);
        rb->joints = NULL;
    }
    destroyAccumulator(p->rigidBodies);
    p->rigidBodies = NULL;

    for (i=0; i<p->num_vanDerWaals; i++) {
        v = p->vanDerWaals[i];
        if (v != NULL) {
            // v->a1 and v->a2 already freed
            // v->parameters still held by vdw hashtable
            free(v);
            p->vanDerWaals[i] = NULL;
        }
    }
    destroyAccumulator(p->vanDerWaals);
    p->vanDerWaals = NULL;
    
    // nothing in a stretch needs freeing
    if (p->stretches != NULL) {
        free(p->stretches);
        p->stretches = NULL;
    }

    // nothing in a bend needs freeing
    if (p->bends != NULL) {
        free(p->bends);
        p->bends = NULL;
    }

    // nothing in a torsion needs freeing
    if (p->torsions != NULL) {
        free(p->torsions);
        p->torsions = NULL;
    }

    // nothing in a cumuleneTorsion needs freeing
    if (p->cumuleneTorsions != NULL) {
        free(p->cumuleneTorsions);
        p->cumuleneTorsions = NULL;
    }

    // nothing in an outOfPlane needs freeing
    if (p->outOfPlanes != NULL) {
        free(p->outOfPlanes);
        p->outOfPlanes = NULL;
    }
    
    free(p);
}

// Add a bond to the bond list for a single atom.
static void
addBondToAtom(struct part *p, struct bond *b, struct atom *a)
{
    int i;
    
    for (i=0; i<a->num_bonds; i++) {
	if (a->bonds[i] == NULL) {
	    a->bonds[i] = b;
	    return;
	}
    }
    ERROR("Internal error: No slot for bond in atom");
    p->parseError(p->stream);
}

// After creating all of the atoms and bonds, we go back and tell each
// atom which bonds it is a part of.
static void
addBondsToAtoms(struct part *p)
{
    int i;
    struct bond *b;
    struct atom *a;
    
    NULLPTR(p);
    for (i=0; i<p->num_bonds; i++) {
	/*
	 * I've seen a few different bugs with null pointers here. We
	 * should try to get a warning of some kind.
	 */
	b = p->bonds[i];
	CHECK_VALID_BOND(b);
	b->a1->num_bonds++;
	b->a2->num_bonds++;
    }
    for (i=0; i<p->num_atoms; i++) {
	a = p->atoms[i];
	a->bonds = (struct bond **)allocate(sizeof(struct bond *) * a->num_bonds);
	memset(a->bonds, 0, sizeof(struct bond *) * a->num_bonds);
    }
    for (i=0; i<p->num_bonds; i++) {
	b = p->bonds[i];
	addBondToAtom(p, b, b->a1);
	addBondToAtom(p, b, b->a2);
    }
}

// Called to indicate that a parser has finished reading data for this
// part.  Finalizes the data structures and switches to the default
// error handler.
struct part *
endPart(struct part *p)
{
    p->parseError = &defaultParseError;
    p->stream = p;
    p->num_vanDerWaals = p->num_static_vanDerWaals;
    
    // XXX realloc any accumulators
    
    addBondsToAtoms(p);

    // other routines should:
    // build stretchs, bends, and torsions
    // calculate initial velocities
    
    return p;
}

void
initializePart(struct part *p)
{
    updateVanDerWaals(p, NULL, p->positions);
    generateStretches(p);
    generateBends(p);
    generateTorsions(p);
    generateOutOfPlanes(p);
    rigid_init(p);
}

// Creates a stretch for each bond in the part.
void
generateStretches(struct part *p)
{
    int i;
    
    p->num_stretches = p->num_bonds;
    p->stretches = (struct stretch *)allocate(sizeof(struct stretch) * p->num_stretches);
    for (i=0; i<p->num_bonds; i++) {
	CHECK_VALID_BOND(p->bonds[i]);
	// XXX skip stretch if both ends are grounded
	p->stretches[i].a1 = p->bonds[i]->a1;
	p->stretches[i].a2 = p->bonds[i]->a2;
	p->stretches[i].b = p->bonds[i];
	// XXX really should send struct atomType instead of protons
	p->stretches[i].stretchType = getBondStretch(p->stretches[i].a1->type->protons,
						     p->stretches[i].a2->type->protons,
						     p->bonds[i]->order);
    }
}

// Fill in the bend data structure for a bend centered on the given
// atom.  The two bonds that make up the bend are indexed in the
// center atom's bond array.
static void
makeBend(struct part *p, int bend_number, struct atom *a, int bond1, int bond2)
{
    struct bend *b;
    
    b = &p->bends[bend_number];
    b->ac = a;
    b->b1 = a->bonds[bond1];
    b->b2 = a->bonds[bond2];

    CHECK_VALID_BOND(b->b1);
    if (b->b1->a1 == a) {
	b->a1 = b->b1->a2;
	b->dir1 = 1;
    } else if (b->b1->a2 == a) {
	b->a1 = b->b1->a1;
	b->dir1 = 0;
    } else {
	// print a better error if it ever happens...
	fprintf(stderr, "neither end of bond on center!");
    }
    
    CHECK_VALID_BOND(b->b2);
    if (b->b2->a1 == a) {
	b->a2 = b->b2->a2;
	b->dir2 = 1;
    } else if (b->b2->a2 == a) {
	b->a2 = b->b2->a1;
	b->dir2 = 0;
    } else {
	// print a better error if it ever happens...
	fprintf(stderr, "neither end of bond on center!");
    }
    
    // XXX should just use atomType instead of protons
    b->bendType = getBendData(a->type->protons,
                              a->hybridization,
			      b->a1->type->protons, b->b1->order,
			      b->a2->type->protons, b->b2->order);
}

// Creates a bend for each pair of adjacent bonds in the part.
void
generateBends(struct part *p)
{
    int i;
    int j;
    int k;
    int bend_index = 0;
    struct atom *a;
    
    // first, count the number of bends
    for (i=0; i<p->num_atoms; i++) {
	a = p->atoms[i];
	for (j=0; j<a->num_bonds; j++) {
	    for (k=j+1; k<a->num_bonds; k++) {
		p->num_bends++;
	    }
	}
    }
    
    p->bends = (struct bend *)allocate(sizeof(struct bend) * p->num_bends);
    
    // now, fill them in (make sure loop structure is same as above)
    for (i=0; i<p->num_atoms; i++) {
	a = p->atoms[i];
	for (j=0; j<a->num_bonds; j++) {
	    for (k=j+1; k<a->num_bonds; k++) {
		makeBend(p, bend_index++, a, j, k);
	    }
	}
    }
}

static void
makeTorsion(struct part *p, int index, struct bond *center, struct bond *b1, struct bond *b2)
{
    struct torsion *t = &(p->torsions[index]);

    t->aa = center->a1;
    t->ab = center->a2;
    t->a1 = b1->a1 == t->aa ? b1->a2 : b1->a1;
    t->a2 = b2->a1 == t->ab ? b2->a2 : b2->a1;

    // Barrior to rotation of a simple alkene is about 265 kJ/mol, but
    // can be on the order of 50 kJ/mol for "captodative ethylenes",
    // where the charge density on the carbons involved in the double
    // bond has been significantly altered.
    // [[Advanced Organic Chemistry, Jerry March, Fourth Edition,
    // Chapter 4, p.129.]]
    // A is in aJ/rad^2, but rotational barrior is 2A
    // 2.65e5 J/mol == 4.4e-19 J/bond
    // A = 2.2e-19 or 0.22 aJ
    t->A = 0.22; // XXX need to get actual value from real parameters
}

// This is called for every double bond in the cumulene chain.  On
// either end of the chain, there should be atoms of sp2
// hybridization.  In the middle, all of the atoms are sp.  This
// routine returns non-zero only when called with b as one of the two
// ending bonds, but not the other one.  When it does return non-zero,
// b2 is filled in with the other ending bond, and aa, ab, ay, and az
// are the atoms on either end of the bonds b and b2.  So, atom aa
// will be sp2, as will az, while ab and ay are sp.  The total number
// of double bonds in the chain (including b and b2) is returned in n.
static int
findCumuleneTorsion(struct bond *b,
                    struct bond **b2,
                    struct atom **aa,
                    struct atom **ab,
                    struct atom **ay,
                    struct atom **az,
                    int *n)
{
    int chainLength;
    struct bond *lastBond;
    struct bond *nextBond;
    struct atom *nextAtom;
    
    if (b->a1->hybridization == sp && b->a2->hybridization == sp) {
        return 0; // middle of the chain.
    }
    if (b->a1->hybridization != sp && b->a2->hybridization != sp) {
        return 0; // not a cumulene
    }
    if (b->a1->hybridization == sp) {
        nextAtom = b->a1;
        *aa = b->a2;
        *ab = b->a1;
    } else {
        nextAtom = b->a2;
        *aa = b->a1;
        *ab = b->a2;
    }
    nextBond = lastBond = b;
    chainLength = 1;
    while (nextAtom->hybridization == sp) {
        if (nextAtom->num_bonds != 2) {
            // XXX complain, I thought this thing was supposed to be sp, that means TWO bonds!
            return 0;
        }
        if (nextAtom->bonds[0] == lastBond) {
            nextBond = nextAtom->bonds[1];
        } else {
            nextBond = nextAtom->bonds[0];
        }
        switch (nextBond->order) {
        case '2':
        case 'a':
        case 'g': // we're being lenient here, a and g don't really make sense
            break;
        default:
            return 0; // chain terminated by a non-double bond, no torsions
        }
        if (nextBond->a1 == nextAtom) {
            nextAtom = nextBond->a2;
        } else {
            nextAtom = nextBond->a1;
        }
        lastBond = nextBond;
        chainLength++;
    }
    if ((*aa)->index >= nextAtom->index) {
        return 0; // only pick one end of the chain
    }
    *az = nextAtom;
    *b2 = nextBond;
    *n = chainLength;
    if (nextBond->a1 == nextAtom) {
        *ay = nextBond->a2;
    } else {
        *ay = nextBond->a1;
    }
    return 1;
}

static void
makeCumuleneTorsion(struct part *p,
                    int index,
                    struct atom *aa,
                    struct atom *ab,
                    struct atom *ay,
                    struct atom *az,
                    int j,
                    int k,
                    int n)
{
    struct cumuleneTorsion *t = &(p->cumuleneTorsions[index]);

    if (aa->bonds[j]->a1 == aa) {
        t->a1 = aa->bonds[j]->a2;
    } else {
        t->a1 = aa->bonds[j]->a1;
    }
    t->aa = aa;
    t->ab = ab;
    t->ay = ay;
    t->az = az;
    if (az->bonds[k]->a1 == az) {
        t->a2 = az->bonds[k]->a2;
    } else {
        t->a2 = az->bonds[k]->a1;
    }
    t->numberOfDoubleBonds = n;
    t->A = 0.22 / ((double)n); // XXX need actual value here
}

// Creates a torsion for each triplet of adjacent bonds in the part,
// where the center bond is graphitic, aromatic, or double.  If one
// end of a double bond is an sp atom, we make a cumuleneTorsion
// instead.
void
generateTorsions(struct part *p)
{
    int i;
    int j;
    int k;
    int torsion_index = 0;
    int cumuleneTorsion_index = 0;
    struct bond *b;
    struct bond *b2;
    struct atom *ct_a;
    struct atom *ct_b;
    struct atom *ct_y;
    struct atom *ct_z;
    int n;
    
    // first, count the number of torsions
    for (i=0; i<p->num_bonds; i++) {
	b = p->bonds[i];
        CHECK_VALID_BOND(b);
        switch (b->order) {
        case 'a':
        case 'g':
        case '2':
            if (b->a1->hybridization == sp || b->a2->hybridization == sp) {
                if (findCumuleneTorsion(b, &b2, &ct_a, &ct_b, &ct_y, &ct_z, &n)) {
                    for (j=0; j<ct_a->num_bonds; j++) {
                        if (ct_a->bonds[j] != b) {
                            for (k=0; k<ct_z->num_bonds; k++) {
                                if (ct_z->bonds[k] != b2) {
                                    p->num_cumuleneTorsions++;
                                }
                            }
                        }
                    }
                }
                break;
            }
            for (j=0; j<b->a1->num_bonds; j++) {
                if (b->a1->bonds[j] != b) {
                    for (k=0; k<b->a2->num_bonds; k++) {
                        if (b->a2->bonds[k] != b) {
                            p->num_torsions++;
                        }
                    }
                }
            }
            break;
        default:
            break;
        }
        
    }
    
    p->torsions = (struct torsion *)allocate(sizeof(struct torsion) * p->num_torsions);
    p->cumuleneTorsions = (struct cumuleneTorsion *)allocate(sizeof(struct cumuleneTorsion) * p->num_cumuleneTorsions);
    
    // now, fill them in (make sure loop structure is same as above)
    for (i=0; i<p->num_bonds; i++) {
	b = p->bonds[i];
        CHECK_VALID_BOND(b);
        switch (b->order) {
        case 'a':
        case 'g':
        case '2':
            if (b->a1->hybridization == sp || b->a2->hybridization == sp) {
                if (findCumuleneTorsion(b, &b2, &ct_a, &ct_b, &ct_y, &ct_z, &n)) {
                    for (j=0; j<ct_a->num_bonds; j++) {
                        if (ct_a->bonds[j] != b) {
                            for (k=0; k<ct_z->num_bonds; k++) {
                                if (ct_z->bonds[k] != b2) {
                                    makeCumuleneTorsion(p, cumuleneTorsion_index++, ct_a, ct_b, ct_y, ct_z, j, k, n);
                                }
                            }
                        }
                    }
                }
                break;
            }
            for (j=0; j<b->a1->num_bonds; j++) {
                if (b->a1->bonds[j] != b) {
                    for (k=0; k<b->a2->num_bonds; k++) {
                        if (b->a2->bonds[k] != b) {
                            makeTorsion(p, torsion_index++, b, b->a1->bonds[j], b->a2->bonds[k]);
                        }
                    }
                }
            }
        default:
            break;
        }
        
    }
}

static void
makeOutOfPlane(struct part *p, int index, struct atom *a)
{
    struct outOfPlane *o = &(p->outOfPlanes[index]);
    struct bond *b;
    
    o->ac = a;
    b = a->bonds[0];
    o->a1 = b->a1 == a ? b->a2 : b->a1;
    b = a->bonds[1];
    o->a2 = b->a1 == a ? b->a2 : b->a1;
    b = a->bonds[2];
    o->a3 = b->a1 == a ? b->a2 : b->a1;

    // A is in aJ/pm^2
    o->A = 0.00025380636; // This is for carbon in graphene with deflection less than 0.5 pm.
    //o->A = 0.0005; // XXX need to get actual value from real parameters
}

// Creates an outOfPlane for each sp2 atom
void
generateOutOfPlanes(struct part *p)
{
    int i;
    int outOfPlane_index = 0;
    struct atom *a;
    
    // first, count the number of outOfPlanes
    for (i=0; i<p->num_atoms; i++) {
	a = p->atoms[i];
        switch (a->hybridization) {
        case sp2:
        case sp2_g:
            if (a->num_bonds == 3) {
                p->num_outOfPlanes++;
            }
        default:
            break;
        }
        
    }
    
    p->outOfPlanes = (struct outOfPlane *)allocate(sizeof(struct outOfPlane) * p->num_outOfPlanes);
    
    // now, fill them in (make sure loop structure is same as above)
    for (i=0; i<p->num_atoms; i++) {
	a = p->atoms[i];
        switch (a->hybridization) {
        case sp2:
        case sp2_g:
            if (a->num_bonds == 3) {
                makeOutOfPlane(p, outOfPlane_index++, a);
            } // else WARNING ???
        default:
            break;
        }
        
    }
}

// use these if the vdw generation code fails to create or destroy an
// interaction when it should, as determined by the verification
// routine.  The grid locations of the two indicated atoms will be
// printed each time, along with indications of when the interaction
// between them is created or destroyed.
//#define TRACK_VDW_PAIR
//#define VDW_FIRST_ATOM_ID 61
//#define VDW_SECOND_ATOM_ID 73

// Scan the dynamic van der Waals list and mark as invalid any
// interaction involving atom a.
static void
invalidateVanDerWaals(struct part *p, struct atom *a)
{
    int i;
    struct vanDerWaals *vdw;
    
    for (i=p->num_static_vanDerWaals; i<p->num_vanDerWaals; i++) {
	vdw = p->vanDerWaals[i];
	if (vdw && (vdw->a1 == a || vdw->a2 == a)) {
#ifdef TRACK_VDW_PAIR
            if (vdw->a1->atomID == VDW_FIRST_ATOM_ID && vdw->a2->atomID == VDW_SECOND_ATOM_ID) {
                fprintf(stderr, "deleting vdw from %d to %d\n", vdw->a1->atomID, vdw->a2->atomID);
            }
#endif
	    p->vanDerWaals[i] = NULL;
	    free(vdw);
	    if (i < p->start_vanDerWaals_free_scan) {
		p->start_vanDerWaals_free_scan = i;
	    }
	}
    }
}

// Find a free slot in the dynamic van der Waals list (either one
// marked invalid above, or a new one appended to the list).  Fill it
// with a new, valid, interaction.
static void
makeDynamicVanDerWaals(struct part *p, struct atom *a1, struct atom *a2)
{
    int i;
    struct vanDerWaals *vdw = NULL;
    
    vdw = (struct vanDerWaals *)allocate(sizeof(struct vanDerWaals));
    
    for (i=p->start_vanDerWaals_free_scan; i<p->num_vanDerWaals; i++) {
	if (!(p->vanDerWaals[i])) {
	    p->vanDerWaals[i] = vdw;
	    p->start_vanDerWaals_free_scan = i + 1;
	    break;
	}
    }
    if (i >= p->num_vanDerWaals) {
	p->num_vanDerWaals++;
	p->vanDerWaals = (struct vanDerWaals **)
	    accumulator(p->vanDerWaals,
			sizeof(struct vanDerWaals *) * p->num_vanDerWaals, 0);
	p->vanDerWaals[p->num_vanDerWaals - 1] = vdw;
	p->start_vanDerWaals_free_scan = p->num_vanDerWaals;
    }
    vdw->a1 = a1;
    vdw->a2 = a2;
    vdw->parameters = getVanDerWaalsTable(a1->type->protons, a2->type->protons);
#ifdef TRACK_VDW_PAIR
    if (a1->atomID == VDW_FIRST_ATOM_ID && a2->atomID == VDW_SECOND_ATOM_ID) {
        fprintf(stderr, "creating vdw from %d to %d\n", a1->atomID, a2->atomID);
    }
#endif
}

// Are a1 and a2 both bonded to the same atom (or to each other)?
static int
isBondedToSame(struct atom *a1, struct atom *a2)
{
    int i;
    int j;
    struct bond *b1;
    struct bond *b2;
    struct atom *ac;
    
    if (a1 == a2) {
        return 1;
    }
    for (i=0; i<a1->num_bonds; i++) {
	b1 = a1->bonds[i];
	ac = (b1->a1 == a1) ? b1->a2 : b1->a1;
	if (ac == a2) {
	    // bonded to each other
	    return 1;
	}
	for (j=0; j<a2->num_bonds; j++) {
	    b2 = a2->bonds[j];
	    if (ac == ((b2->a1 == a2) ? b2->a2 : b2->a1)) {
		// both bonded to common atom ac
		return 1;
	    }
	}
    }
    return 0;
}

static void
verifyVanDerWaals(struct part *p, struct xyz *positions)
{
    int *seen;
    int i;
    int j;
    int k;
    struct atom *a1, *a2;
    double r1, r2;
    int i1, i2;
    struct xyz p1, p2;
    struct vanDerWaals *vdw;
    double rvdw;
    double distance;
    int found;
    int actual_count;
    int notseen_count;

    seen = (int *)allocate(sizeof(int) * p->num_vanDerWaals);
    // wware 060109  python exception handling
    NULLPTR(seen);
    for (i=0; i<p->num_vanDerWaals; i++) {
	seen[i] = 0;
    }
    
    for (j=0; j<p->num_atoms; j++) {
	a1 = p->atoms[j];
	i1 = a1->index;
	r1 = a1->type->vanDerWaalsRadius; // angstroms
	p1 = positions[i1];
	for (k=j+1; k<p->num_atoms; k++) {
	    a2 = p->atoms[k];
	    if (!isBondedToSame(a1, a2)) {
		i2 = a2->index;
		r2 = a2->type->vanDerWaalsRadius; // angstroms
		p2 = positions[i2];
		rvdw = (r1 + r2) * 100.0; // picometers
		distance = vlen(vdif(p1, p2));
		if (distance < rvdw * VanDerWaalsCutoffFactor) {
		    found = 0;
		    for (i=0; i<p->num_vanDerWaals; i++) {
			vdw = p->vanDerWaals[i];
			if (vdw != NULL) {
			    CHECK_VALID_BOND(vdw);
			    if (vdw->a1 == a1 && vdw->a2 == a2) {
				seen[i] = 1;
				found = 1;
				break;
			    }
			}
		    }
		    if (!found) {
			testAlert("missing vdw: a1:");
			printAtomShort(stderr, a1);
			testAlert(" a2:");
			printAtomShort(stderr, a2);
			testAlert(" distance: %f rvdw: %f\n", distance, rvdw);
		    }
		}
	    }
	}
    }
    actual_count = 0;
    notseen_count = 0;
    for (i=0; i<p->num_vanDerWaals; i++) {
	vdw = p->vanDerWaals[i];
	if (vdw != NULL) {
	    actual_count++;
	    if (!seen[i]) {
		notseen_count++;
		CHECK_VALID_BOND(vdw);
		p1 = positions[vdw->a1->index];
		p2 = positions[vdw->a2->index];
		distance = vlen(vdif(p1, p2));
		r1 = vdw->a1->type->vanDerWaalsRadius; // angstroms
		r2 = vdw->a2->type->vanDerWaalsRadius; // angstroms
		rvdw = (r1 + r2) * 100.0; // picometers
		if (distance < rvdw * VanDerWaalsCutoffFactor) {
		    testAlert("should have found this one above!!!\n");
		}
		if (distance > rvdw * VanDerWaalsCutoffFactor + 2079.0) { // was 866.0
		    testAlert("unnecessary vdw: a1:");
		    printAtomShort(stderr, vdw->a1);
		    testAlert(" a2:");
		    printAtomShort(stderr, vdw->a2);
		    testAlert(" distance: %f rvdw: %f\n", distance, rvdw);
		}
	    }
	}
    }
    //testAlert("num_vdw: %d actual_count: %d not_seen: %d\n", p->num_vanDerWaals, actual_count, notseen_count);
    free(seen); // yes, alloca would work here too.
}

// All of space is divided into a cubic grid with each cube being
// GRID_SPACING pm on a side.  Every GRID_OCCUPANCY cubes in each
// direction there is a bucket.  Every GRID_SIZE buckets the grid
// wraps back on itself, so that each bucket stores atoms that are in
// an infinite number of grid cubes, where the cubes are some multiple
// of GRID_SPACING * GRID_OCCUPANCY * GRID_SIZE pm apart.  GRID_SIZE
// must be a power of two, so the index along a particular dimension
// of the bucket array where a particular coordinates is found is
// calculated with: (int(x/GRID_SPACING) * GRID_OCCUPANCY) &
// (GRID_SIZE-1).
//
// Buckets can overlap.  When deciding if an atom is still in the same
// bucket, a fuzzy match is used, masking off one or more low order
// bits of the bucket array index.  When an atom leaves a bucket
// according to the fuzzy matching, it is placed in a new bucket based
// on the non-fuzzy index into the bucket array.  In this way, an atom
// vibrating less than the bucket overlap distance will remain in the
// same bucket irrespective of it's position with respect to the grid
// while it is vibrating.
//
// The fuzzy match looks like this: moved = (current - previous) &
// GRID_MASK.  GRID_MASK is (GRID_SIZE-1) with one or more low order
// bits zeroed.  It works correctly if the subtraction is done two's
// complement, it may not for one's complement subtraction.  With no
// bits zeroed, there is no overlap.  With one zero, the buckets
// overlap by 50%.  Two zeros = 3/4 overlap.  Three zeros = 7/8
// overlap.  The above are if GRID_OCCUPANCY == 1.  Larger values for
// GRID_OCCUPANCY allow overlaps between zero and 50%.
//
// Current algorithm is written for 50% overlap, so GRID_OCCUPANCY is
// assumed to be 1, simplifing the code.
//
// GRID_FUZZY_BUCKET_WIDTH is the size of a fuzzy bucket in bucket
// units.  For a 50% overlap it has the value 2.



// Update the dynamic van der Waals list for this part.  Validity is a
// tag to prevent rescanning the same configuration a second time.
void
updateVanDerWaals(struct part *p, void *validity, struct xyz *positions)
{
    int i;
    int ax;
    int ay;
    int az;
    int ax2;
    int ay2;
    int az2;
    struct atom *a;
    struct atom *a2;
    struct atom **bucket;
    double r;
    double rSquared;
    double actualR;
    struct xyz dr;
    double drSquared;
    int dx;
    int dy;
    int dz;
    double deltax;
    double deltay;
    double deltaz;
    double deltaXSquared;
    double deltaYSquared;
    double deltaZSquared;
    int signx;
    int signy;
    int signz;

    // wware 060109  python exception handling
    NULLPTR(p);
    if (validity && p->vanDerWaals_validity == validity) {
	return;
    }
    if (p->num_atoms <= 0) {
        return;
    }
    NULLPTR(positions);
    for (i=0; i<p->num_atoms; i++) {
	a = p->atoms[i];
	ax = (int)(positions[i].x / GRID_SPACING);
	ay = (int)(positions[i].y / GRID_SPACING);
	az = (int)(positions[i].z / GRID_SPACING);

#ifdef TRACK_VDW_PAIR
        if (a->atomID == VDW_FIRST_ATOM_ID || a->atomID == VDW_SECOND_ATOM_ID) {
            fprintf(stderr, "%d (%d, %d, %d) Iteration %d\n", a->atomID, ax, ay, az, Iteration);
        }
#endif
	if (a->vdwBucketInvalid ||
            (ax - a->vdwBucketIndexX) & GRID_MASK_FUZZY ||
            (ay - a->vdwBucketIndexY) & GRID_MASK_FUZZY ||
            (az - a->vdwBucketIndexZ) & GRID_MASK_FUZZY) {

	    invalidateVanDerWaals(p, a);
	    // remove a from it's old bucket chain
	    if (a->vdwNext) {
		a->vdwNext->vdwPrev = a->vdwPrev;
	    }
	    if (a->vdwPrev) {
		a->vdwPrev->vdwNext = a->vdwNext;
	    } else {
                bucket = &(p->vdwHash[a->vdwBucketIndexX][a->vdwBucketIndexY][a->vdwBucketIndexZ]);
                if (*bucket == a) {
                    *bucket = a->vdwNext;
                }
	    }
	    // and add it to the new one
            a->vdwBucketIndexX = ax & GRID_MASK;
            a->vdwBucketIndexY = ay & GRID_MASK;
            a->vdwBucketIndexZ = az & GRID_MASK;
            a->vdwBucketInvalid = 0;
            bucket = &(p->vdwHash[a->vdwBucketIndexX][a->vdwBucketIndexY][a->vdwBucketIndexZ]);
            
	    a->vdwNext = *bucket;
	    a->vdwPrev = NULL;
	    *bucket = a;
	    if (a->vdwNext) {
		a->vdwNext->vdwPrev = a;
	    }
            r = (a->type->vanDerWaalsRadius * 100.0 + MAX_VDW_RADIUS) * VanDerWaalsCutoffFactor;
            rSquared = r * r;
            dx = 0;
            while (1) {
                // deltax is the minimum distance along the x axis
                // between the fuzzy edges of the two buckets we're
                // looking at.  Both atoms can move within their
                // respective fuzzy buckets and will never get closer
                // than this along the x axis.  If the fuzzy buckets
                // overlap, or share an edge, the distance is zero.
                deltax = (dx-GRID_FUZZY_BUCKET_WIDTH > 0 ? dx-GRID_FUZZY_BUCKET_WIDTH : 0) * GRID_SPACING;
                if (deltax > r) {
                    break;
                }
                deltaXSquared = deltax * deltax;
                for (signx=-1; signx<=1; signx+=2) {
                    if (signx > 0 || dx > 0) {
                        ax2 = ax + dx * signx;
                        
                        dy = 0;
                        while (1) {
                            deltay = (dy-GRID_FUZZY_BUCKET_WIDTH > 0 ? dy-GRID_FUZZY_BUCKET_WIDTH : 0) * GRID_SPACING;
                            deltaYSquared = deltay * deltay;
                            if (deltaXSquared + deltaYSquared > rSquared) {
                                break;
                            }
                            for (signy=-1; signy<=1; signy+=2) {
                                if (signy > 0 || dy > 0) {
                                    ay2 = ay + dy * signy;

                                    dz = 0;
                                    while (1) {
                                        deltaz = (dz-GRID_FUZZY_BUCKET_WIDTH > 0 ? dz-GRID_FUZZY_BUCKET_WIDTH : 0) * GRID_SPACING;
                                        deltaZSquared = deltaz * deltaz;
                                        if (deltaXSquared +
                                            deltaYSquared +
                                            deltaZSquared > rSquared) {
                                            break;
                                        }
                                        for (signz=-1; signz<=1; signz+=2) {
                                            if (signz > 0 || dz > 0) {
                                                az2 = az + dz * signz;
                                                // We hit this point in the code once for each bucket
                                                // that could contain an atom of any type which is
                                                // within the maximum vdw cutoff radius.

                                                a2 = p->vdwHash[ax2&GRID_MASK][ay2&GRID_MASK][az2&GRID_MASK];
                                                for (; a2 != NULL; a2=a2->vdwNext) {
                                                    if (!isBondedToSame(a, a2)) {
                                                        // At this point, we know the types of both
                                                        // atoms, so we can eliminate buckets which
                                                        // might be in range for some atom types,
                                                        // but not for this one.
                                                        actualR = (a->type->vanDerWaalsRadius * 100.0 +
                                                                   a2->type->vanDerWaalsRadius * 100.0)
                                                            * VanDerWaalsCutoffFactor;
                                                        if (deltaXSquared +
                                                            deltaYSquared +
                                                            deltaZSquared > (actualR * actualR)) {
                                                            continue;
                                                        }
                                                        // Now we check to see if the two atoms are
                                                        // actually within the same wrapping of the
                                                        // grid.  Just because they're in nearby
                                                        // buckets, it doesn't mean that they are
                                                        // actually near each other.  This check is
                                                        // very coarse, because we've already
                                                        // eliminated intermediate distances.
                                                        dr = vdif(positions[i], positions[a2->index]);
                                                        drSquared = vdot(dr, dr);
                                                        if (drSquared < GRID_WRAP_COMPARE * GRID_WRAP_COMPARE) {
                                                            // We insure that all vdw's are created
                                                            // with the first atom of lower index
                                                            // than the second.
                                                            if (i < a2->index) {
                                                                makeDynamicVanDerWaals(p, a, a2); BAIL();
                                                            } else {
                                                                makeDynamicVanDerWaals(p, a2, a); BAIL();
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        dz++;
                                    }
                                }
                            }
                            dy++;
                        }
                    }
                }
                dx++;
            }
        }
    }
    p->vanDerWaals_validity = validity;
    if (DEBUG(D_VERIFY_VDW)) { // -D13
	// wware 060109  python exception handling
	verifyVanDerWaals(p, positions); BAIL();
    }
}

// Returns an entry in the p->atoms array, given an external atom id
// (as used in an mmp file, for example).
static struct atom *
translateAtomID(struct part *p, int atomID)
{
    int atomIndex;
    
    if (atomID < 0 || atomID > p->max_atom_id) {
	ERROR2("atom ID %d out of range [0, %d]", atomID, p->max_atom_id);
	p->parseError(p->stream);
    }
    atomIndex = p->atom_id_to_index_plus_one[atomID] - 1;
    if (atomIndex < 0) {
	ERROR1("atom ID %d not yet encountered", atomID);
	p->parseError(p->stream);
    }
    return p->atoms[atomIndex];
}

// gaussianDistribution() and gxyz() are also used by the thermostat jig...

// generate a random number with a gaussian distribution
//
// see Knuth, Vol 2, 3.4.1.C
static double
gaussianDistribution(double mean, double stddev)
{
    double v0,v1, rSquared;
    
    do {
	// generate random numbers in the range [-1.0 .. 1.0]
	v0=(float)rand()/(float)(RAND_MAX/2) - 1.0;
	v1=(float)rand()/(float)(RAND_MAX/2) - 1.0;
	rSquared = v0*v0 + v1*v1;
    } while (rSquared>=1.0 || rSquared==0.0);
    // v0 and v1 are uniformly distributed within a unit circle
    // (excluding the origin)
    return mean + stddev * v0 * sqrt(-2.0 * log(rSquared) / rSquared);
}

// Generates a gaussian distributed random velocity for a range of
// atoms, scaled by 1/sqrt(mass).  The result array must be
// preallocated by the caller.
static void
generateRandomVelocities(struct part *p, struct xyz *velocity, int firstAtom, int lastAtom)
{
    int i;
    double stddev;
    
    for (i=firstAtom; i<=lastAtom; i++) {
        stddev = sqrt(2.0 * Boltz * Temperature / (p->atoms[i]->mass * 1e-27)) * Dt / Dx;
        velocity[i].x = gaussianDistribution(0.0, stddev);
        velocity[i].y = gaussianDistribution(0.0, stddev);
        velocity[i].z = gaussianDistribution(0.0, stddev);
    }
}

// Find the center of mass of a range of atoms in the part.
static struct xyz
findCenterOfMass(struct part *p, struct xyz *position, int firstAtom, int lastAtom)
{
    struct xyz com;
    struct xyz a;
    double mass;
    double totalMass = 0.0;
    int i;

    vsetc(com, 0.0);
    for (i=firstAtom; i<=lastAtom; i++) {
        mass = p->atoms[i]->mass;
        vmul2c(a, position[i], mass);
        vadd(com, a);
        totalMass += mass;
    }
    if (fabs(totalMass) > 1e-20) {
        vmulc(com, 1.0/totalMass);
    }
    return com;
}

static double
findTotalMass(struct part *p, int firstAtom, int lastAtom)
{
    double mass = 0.0;
    int i;

    for (i=firstAtom; i<=lastAtom; i++) {
        mass += p->atoms[i]->mass;
    }
    return mass;
}

static struct xyz
findAngularMomentum(struct part *p, struct xyz center, struct xyz *position, struct xyz *velocity, int firstAtom, int lastAtom)
{
    int i;
    struct xyz total_angular_momentum;
    struct xyz ap;
    struct xyz r;
    double mass;
    
    vsetc(total_angular_momentum, 0.0);
    for (i=firstAtom; i<=lastAtom; i++) {
        mass = p->atoms[i]->mass;
        vsub2(r, position[i], center);
        v2x(ap, r, velocity[i]);         // ap = r x (velocity * mass)
        vmulc(ap, mass);
        vadd(total_angular_momentum, ap);
    }
    return total_angular_momentum;
}

static struct xyz
findLinearMomentum(struct part *p, struct xyz *velocity, int firstAtom, int lastAtom)
{
    int i;
    struct xyz total_momentum;
    struct xyz momentum;
    double mass;
    
    vsetc(total_momentum, 0.0);
    for (i=firstAtom; i<=lastAtom; i++) {
        mass = p->atoms[i]->mass;
        vmul2c(momentum, velocity[i], mass);
        vadd(total_momentum, momentum);
    }
    return total_momentum;
}

static double
findMomentOfInertiaTensorComponent(struct part *p,
                                   struct xyz *position,
                                   struct xyz com,
                                   int axis1,
                                   int axis2,
                                   int firstAtom,
                                   int lastAtom)
{
    int i;
    struct xyza *com_a = (struct xyza *)(&com);
    struct xyza *position_a = (struct xyza *)position;
    double delta_axis1;
    double delta_axis2;
    double mass;
    double ret = 0.0;
    
    if (axis1 == axis2) {
        // I_xx = sum(m * (y^2 + z^2))
        axis1 = (axis1 + 1) % 3;
        axis2 = (axis2 + 2) % 3;
        for (i=firstAtom; i<=lastAtom; i++) {
            mass = p->atoms[i]->mass;
            delta_axis1 = position_a[i].a[axis1] - com_a->a[axis1];
            delta_axis2 = position_a[i].a[axis2] - com_a->a[axis2];
            ret += mass * (delta_axis1 * delta_axis1 + delta_axis2 * delta_axis2);
        }
    } else {
        // I_xy = -sum(m * x * y)
        for (i=firstAtom; i<=lastAtom; i++) {
            mass = p->atoms[i]->mass;
            delta_axis1 = position_a[i].a[axis1] - com_a->a[axis1];
            delta_axis2 = position_a[i].a[axis2] - com_a->a[axis2];
            ret -= mass * delta_axis1 * delta_axis2;
        }
    }
    return ret;
}


static void
findMomentOfInertiaTensor(struct part *p,
                          struct xyz *position,
                          struct xyz com,
                          double *inertia_tensor,
                          int firstAtom,
                          int lastAtom)
{
    inertia_tensor[0] = findMomentOfInertiaTensorComponent(p, position, com, 0, 0, firstAtom, lastAtom); // xx
    inertia_tensor[1] = findMomentOfInertiaTensorComponent(p, position, com, 0, 1, firstAtom, lastAtom); // xy
    inertia_tensor[2] = findMomentOfInertiaTensorComponent(p, position, com, 0, 2, firstAtom, lastAtom); // xz

    inertia_tensor[3] = inertia_tensor[1]; // yx = xy
    inertia_tensor[4] = findMomentOfInertiaTensorComponent(p, position, com, 1, 1, firstAtom, lastAtom); // yy
    inertia_tensor[5] = findMomentOfInertiaTensorComponent(p, position, com, 1, 2, firstAtom, lastAtom); // yz

    inertia_tensor[6] = inertia_tensor[2]; // zx = xz
    inertia_tensor[7] = inertia_tensor[5]; // zy = yz
    inertia_tensor[8] = findMomentOfInertiaTensorComponent(p, position, com, 2, 2, firstAtom, lastAtom); // zz
}

static void
addAngularVelocity(struct xyz center,
                   struct xyz dav,
                   struct xyz *position,
                   struct xyz *velocity,
                   int firstAtom,
                   int lastAtom)
{
    int i;
    struct xyz r;
    struct xyz davxr;
        
    for (i=firstAtom; i<=lastAtom; i++) {
        vsub2(r, position[i], center);
        v2x(davxr, dav, r);
        vadd(velocity[i], davxr);
    }
}

static void
addLinearVelocity(struct xyz dv,
                  struct xyz *velocity,
                  int firstAtom,
                  int lastAtom)
{
    int i;
    
    for (i=firstAtom; i<=lastAtom; i++) {
        vadd(velocity[i], dv);
    }
}

#if 0
static void
printPositionVelocity(struct xyz *position, struct xyz *velocity, int firstAtom, int lastAtom)
{
    int i;
    
    for (i=firstAtom; i<=lastAtom; i++) {
        printf("%d: (%7.3f, %7.3f, %7.3f) (%7.3f, %7.3f, %7.3f)\n",
               i,
               position[i].x,
               position[i].y,
               position[i].z,
               velocity[i].x,
               velocity[i].y,
               velocity[i].z);
    }
    printf("\n");
}

static void
printMomenta(struct part *p, struct xyz *position, struct xyz *velocity, int firstAtom, int lastAtom)
{
    struct xyz com;
    struct xyz total_linear_momentum;
    struct xyz total_angular_momentum;
    
    com = findCenterOfMass(p, position, firstAtom, lastAtom);
    printf("center of mass: (%f, %f, %f)\n", com.x, com.y, com.z);
    total_linear_momentum = findLinearMomentum(p, velocity, firstAtom, lastAtom);
    printf("total_linear_momentum: (%f, %f, %f)\n", total_linear_momentum.x, total_linear_momentum.y, total_linear_momentum.z);

    total_angular_momentum = findAngularMomentum(p, com, position, velocity, firstAtom, lastAtom);
    printf("total_angular_momentum: (%f, %f, %f)\n", total_angular_momentum.x, total_angular_momentum.y, total_angular_momentum.z);
    printPositionVelocity(position, velocity, firstAtom, lastAtom);
}
#endif

// Alter the given velocities for a range of atoms to remove any
// translational motion, and any rotation around their center of mass.
static void
neutralizeMomentum(struct part *p, struct xyz *position, struct xyz *velocity, int firstAtom, int lastAtom)
{
    struct xyz total_linear_momentum;
    struct xyz total_angular_momentum;
    struct xyz com;
    struct xyz dv;
    struct xyz dav;
    double inverseTotalMass;
    double momentOfInertiaTensor[9];
    double momentOfInertiaTensorInverse[9];

    com = findCenterOfMass(p, position, firstAtom, lastAtom);
    inverseTotalMass = 1.0 / findTotalMass(p, firstAtom, lastAtom);

    total_angular_momentum = findAngularMomentum(p, com, position, velocity, firstAtom, lastAtom);
    findMomentOfInertiaTensor(p, position, com, momentOfInertiaTensor, firstAtom, lastAtom);
    if (matrixInvert3(momentOfInertiaTensorInverse, momentOfInertiaTensor)) {
        matrixTransform(&dav, momentOfInertiaTensorInverse, &total_angular_momentum);
        vmulc(dav, -1.0);
        addAngularVelocity(com, dav, position, velocity, firstAtom, lastAtom);
    }

    total_linear_momentum = findLinearMomentum(p, velocity, firstAtom, lastAtom);
    vmul2c(dv, total_linear_momentum, -inverseTotalMass);
    addLinearVelocity(dv, velocity, firstAtom, lastAtom);
}

// Change the given velocities of a range of atoms so that their
// kinetic energies are scaled by the given factor.
static void
scaleKinetic(struct xyz *velocity, double factor, int firstAtom, int lastAtom)
{
    int i;
    double velocity_factor = sqrt(factor);

    // ke_old = m v_old^2 / 2
    // ke_new = m v_new^2 / 2 = factor ke_old = factor (m v_old^2 / 2)
    // m v_new^2 = factor m v_old^2
    // v_new^2 = factor v_old^2
    // v_new = sqrt(factor) v_old
    
    for (i=firstAtom; i<=lastAtom; i++) {
        vmulc(velocity[i], velocity_factor);
    }
}

void
setThermalVelocities(struct part *p, double temperature)
{
    int firstAtom = 0;
    int lastAtom = p->num_atoms-1;
    int dof; // degrees of freedom
    int i = 0;
    double initial_temp;

    if (p->num_atoms == 1 || temperature < 1e-8) {
        return;
    }
    // probably should be 3N-6, but the thermometer doesn't know that
    // the linear and angular momentum have been cancelled.
    dof = 3 * p->num_atoms;
    if (dof < 1) {
        dof = 1;
    }

    initial_temp = 0.0;
    while (fabs(initial_temp) < 1e-8) {
        generateRandomVelocities(p, p->velocities, firstAtom, lastAtom);
        neutralizeMomentum(p, p->positions, p->velocities, firstAtom, lastAtom);

        // kinetic = 3 k T / 2
        // T = kinetic 2 / 3 k
        // calculateKinetic() returns aJ (1e-18 J), so we get Kelvins:

        initial_temp = calculateKinetic(p) * 2.0 * 1e-18 / (Boltz * ((double)dof));
        if (++i > 10) {
            ERROR("unable to set initial temperature");
            return;
        }
    }

    // We scale to get to twice the target temperature, because we're
    // assuming the part has been minimized, and the energy will be
    // divided between kinetic and potential energy.
    scaleKinetic(p->velocities, 2.0 * temperature / initial_temp, firstAtom, lastAtom);
}


// Add an atom to the part.  ExternalID is the atom number as it
// appears in (for example) an mmp file.  ElementType is the number of
// protons (XXX should really be an atomType).
void
makeAtom(struct part *p, int externalID, int elementType, struct xyz position)
{
    double mass;
    struct atom *a;
    
    if (externalID < 0) {
	ERROR1("atom ID %d must be >= 0", externalID);
	p->parseError(p->stream);
    }
    if (externalID > p->max_atom_id) {
	p->max_atom_id = externalID;
	p->atom_id_to_index_plus_one = (int *)accumulator(p->atom_id_to_index_plus_one,
							  sizeof(int) * (p->max_atom_id + 1), 1);
    }
    if (p->atom_id_to_index_plus_one[externalID]) {
	ERROR2("atom ID %d already defined with index %d", externalID, p->atom_id_to_index_plus_one[externalID] - 1);
	p->parseError(p->stream);
    }
    p->atom_id_to_index_plus_one[externalID] = ++(p->num_atoms);
    
    p->atoms = (struct atom **)accumulator(p->atoms, sizeof(struct atom *) * p->num_atoms, 0);
    p->positions = (struct xyz *)accumulator(p->positions, sizeof(struct xyz) * p->num_atoms, 0);
    p->velocities = (struct xyz *)accumulator(p->velocities, sizeof(struct xyz) * p->num_atoms, 0);
    
    a = (struct atom *)allocate(sizeof(struct atom));
    p->atoms[p->num_atoms - 1] = a;
    a->index = p->num_atoms - 1;
    a->atomID = externalID;
    
    vset(p->positions[a->index], position);
    vsetc(p->velocities[a->index], 0.0);
    
    if (elementType < 0 || elementType > MAX_ELEMENT) {
	ERROR1("Invalid element type: %d", elementType);
	p->parseError(p->stream);
    }
    a->type = &periodicTable[elementType];
    if (a->type->name == NULL) {
	ERROR1("Unsupported element type: %d", elementType);
	p->parseError(p->stream);
    }
    
    a->isGrounded = 0;
    a->num_bonds = 0;
    a->bonds = NULL;
    a->vdwBucketIndexX = 0;
    a->vdwBucketIndexY = 0;
    a->vdwBucketIndexZ = 0;
    a->vdwBucketInvalid = 1;
    a->vdwPrev = NULL;
    a->vdwNext = NULL;
    if (a->type->group == 3) {
        a->hybridization = sp2;
    } else {
        a->hybridization = sp3;
    }
    
    mass = a->type->mass * 1e-27;
    a->mass = a->type->mass;
    a->inverseMass = Dt * Dt / mass;
}

void
setAtomHybridization(struct part *p, int atomID, enum hybridization h)
{
    struct atom *a;
    
    if (atomID < 0 || atomID > p->max_atom_id || p->atom_id_to_index_plus_one[atomID] < 1) {
	ERROR1("setAtomHybridization: atom ID %d not seen yet", atomID);
	p->parseError(p->stream);
    }
    a = p->atoms[p->atom_id_to_index_plus_one[atomID] - 1];
    a->hybridization = h;
}

// Add a new bond to this part.  The atomID's are the external atom
// numbers as found in an mmp file (for example).
void
makeBond(struct part *p, int atomID1, int atomID2, char order)
{
    struct bond *b;
    
    /*********************************************************************/
    // patch to pretend that carbomeric bonds are the same as double bonds
    if (order == 'c') {
	order = '2';
    }
    /*********************************************************************/
    
    p->num_bonds++;
    p->bonds = (struct bond **)accumulator(p->bonds, sizeof(struct bond *) * p->num_bonds, 0);
    b = (struct bond *)allocate(sizeof(struct bond));
    p->bonds[p->num_bonds - 1] = b;
    b->a1 = translateAtomID(p, atomID1);
    b->a2 = translateAtomID(p, atomID2);
    CHECK_VALID_BOND(b);
    // XXX should we reject unknown bond orders here?
    b->order = order;
    b->valid = -1;
}

// Add a static van der Waals interaction between a pair of bonded
// atoms.  Not needed unless you want the vDW on directly bonded
// atoms, as all other vDW interactions will be automatically found.
void
makeVanDerWaals(struct part *p, int atomID1, int atomID2)
{
    struct vanDerWaals *v;
    
    p->num_static_vanDerWaals++;
    p->vanDerWaals = (struct vanDerWaals **)accumulator(p->vanDerWaals, sizeof(struct vanDerWaals *) * p->num_static_vanDerWaals, 0);
    v = (struct vanDerWaals *)allocate(sizeof(struct vanDerWaals));
    p->vanDerWaals[p->num_static_vanDerWaals - 1] = v;
    v->a1 = translateAtomID(p, atomID1);
    v->a2 = translateAtomID(p, atomID2);
    CHECK_VALID_BOND(v);
    v->parameters = getVanDerWaalsTable(v->a1->type->protons, v->a2->type->protons);
}

// Compute Sum(1/2*m*v**2) over all the atoms. This is valid ONLY if
// part->velocities has been updated in dynamicsMovie().
double
calculateKinetic(struct part *p)
{
    struct xyz *velocities = p->velocities;
    double total = 0.0;
    int j;
    for (j=0; j<p->num_atoms; j++) {
	struct atom *a = p->atoms[j];
        // v in pm/Dt
	double v = vlen(velocities[a->index]);
        // mass in yg (1e-24 g)
	// save the factor of 1/2 for later, to keep this loop fast
	total += a->mass * v * v;
    }
    // We want energy in attojoules to be consistent with potential energy
    // mass is in units of Dmass kilograms (Dmass = 1e-27, for mass in yg)
    // velocity is in Dx meters per Dt seconds
    // total is in units of (Dmass Dx^2/Dt^2) joules
    // we want attojoules or 1e-18 joules, so we need to multiply by 1e18
    // and we need the factor of 1/2 that we left out of the atom loop
    return total * 0.5 * 1e18 * Dmass * Dx * Dx / (Dt * Dt);
}

void
makeRigidBody(struct part *p, char *name, double mass, double *inertiaTensor, struct xyz position, struct quaternion orientation)
{
    struct rigidBody *rb;
    int i;
    
    p->num_rigidBodies++;
    p->rigidBodies = (struct rigidBody *)accumulator(p->rigidBodies, p->num_rigidBodies * sizeof(struct rigidBody), 0);
    rb = &p->rigidBodies[p->num_rigidBodies - 1];
    rb->name = name;
    rb->num_stations = 0;
    rb->stations = NULL;
    rb->stationNames = NULL;
    rb->num_axies = 0;
    rb->axies = NULL;
    rb->axisNames = NULL;
    for (i=0; i<6; i++) {
        rb->inertiaTensor[i] = inertiaTensor[i];
    }
    rb->mass = mass;
    rb->position = position;
    vsetc(rb->velocity, 0.0);
    rb->orientation = orientation;
    vsetc(rb->rotation, 0.0);
    rb->num_joints = 0;
    rb->joints = NULL;
}

void
makeStationPoint(struct part *p, char *bodyName, char *stationName, struct xyz position)
{
    int i;
    struct rigidBody *rb;
    
    for (i=p->num_rigidBodies-1; i>=0; i--) {
        if (!strcmp(p->rigidBodies[i].name, bodyName)) {
            rb = &p->rigidBodies[i];
            rb->num_stations++;
            rb->stations = (struct xyz *)accumulator(rb->stations, rb->num_stations * sizeof (struct xyz), 0);
            rb->stationNames = (char **)accumulator(rb->stationNames, rb->num_stations * sizeof (char *), 0);
            rb->stations[rb->num_stations-1] = position;
            rb->stationNames[rb->num_stations-1] = stationName;
            return;
        }
    }
    ERROR1("rigidBody named (%s) not found", bodyName);
    p->parseError(p->stream);
}

void
makeBodyAxis(struct part *p, char *bodyName, char *axisName, struct xyz orientation)
{
    int i;
    struct rigidBody *rb;
    
    for (i=p->num_rigidBodies-1; i>=0; i--) {
        if (!strcmp(p->rigidBodies[i].name, bodyName)) {
            rb = &p->rigidBodies[i];
            rb->num_axies++;
            rb->axies = (struct xyz *)accumulator(rb->axies, rb->num_axies * sizeof (struct xyz), 0);
            rb->axisNames = (char **)accumulator(rb->axisNames, rb->num_axies * sizeof (char *), 0);
            rb->axies[rb->num_axies-1] = orientation;
            rb->axisNames[rb->num_axies-1] = axisName;
            return;
        }
    }
    ERROR1("rigidBody named (%s) not found", bodyName);
    p->parseError(p->stream);
}

static struct jig *
newJig(struct part *p)
{
    struct jig *j;
    
    p->num_jigs++;
    p->jigs = (struct jig **)accumulator(p->jigs, sizeof(struct jig *) * p->num_jigs, 0);
    j = (struct jig *)allocate(sizeof(struct jig));
    p->jigs[p->num_jigs - 1] = j;

    j->name = NULL;
    j->num_atoms = 0;
    j->atoms = NULL;
    j->degreesOfFreedom = 0;
    j->coordinateIndex = 0;
    j->data = 0.0;
    j->data2 = 0.0;
    j->xdata.x = 0.0;
    j->xdata.y = 0.0;
    j->xdata.z = 0.0;
    
    return j;
}

// Turn an atomID list into an array of struct atom's inside a jig.
static void
jigAtomList(struct part *p, struct jig *j, int atomListLength, int *atomList)
{
    int i;
    
    j->atoms = (struct atom **)allocate(sizeof(struct atom *) * atomListLength);
    j->num_atoms = atomListLength;
    for (i=0; i<atomListLength; i++) {
	j->atoms[i] = translateAtomID(p, atomList[i]);
    }
}

// Turn a pair of atomID's into an array of struct atom's inside a
// jig.  All atoms between the given ID's (inclusive) are included in
// the jig.
static void
jigAtomRange(struct part *p, struct jig *j, int firstID, int lastID)
{
    int len = lastID < firstID ? 0 : 1 + lastID - firstID;
    int id;
    int i;
    
    j->atoms = (struct atom **)allocate(sizeof(struct atom *) * len);
    j->num_atoms = len;
    for (i=0, id=firstID; id<=lastID; i++, id++) {
	j->atoms[i] = translateAtomID(p, id);
    }
}

// Create a ground jig in this part, given the jig name, and the list
// of atoms in the jig.  Atoms in the ground jig will not move.
void
makeGround(struct part *p, char *name, int atomListLength, int *atomList)
{
    int i;
    struct jig *j = newJig(p);
    
    j->type = Ground;
    j->name = name;
    jigAtomList(p, j, atomListLength, atomList);
    for (i=0; i<atomListLength; i++) {
	j->atoms[i]->isGrounded = 1;
        // The following lines test energy conservation of systems
        // with grounds.  Do a dynamics run without these lines,
        // saving the result.  Then comment these lines in and rerun
        // the dynamics run.  Make sure the computed velocities at the
        // beginning of the run are identical.  It's simplest to just
        // do the run at 0 K.  Start with a slightly strained
        // structure to get some motion.  The results should be
        // identical between the two runs.

        //j->atoms[i]->mass *= 100.0;
        //j->atoms[i]->inverseMass = Dt * Dt / (j->atoms[i]->mass * 1e-27);
    }
}


// Create a thermometer jig in this part, given the jig name, and the
// range of atoms to include in the jig.  The Temperature of the atoms
// in the jig will be reported in the trace file.
void
makeThermometer(struct part *p, char *name, int firstAtomID, int lastAtomID)
{
    struct jig *j = newJig(p);
    
    j->type = Thermometer;
    j->name = name;
    jigAtomRange(p, j, firstAtomID, lastAtomID);
}

// Create an dihedral meter jig in this part, given the jig name, and the
// three atoms to measure.  The dihedral angle between the atoms will be
// reported in the trace file.
void
makeDihedralMeter(struct part *p, char *name, int atomID1, int atomID2, int atomID3, int atomID4)
{
    struct jig *j = newJig(p);
    
    j->type = DihedralMeter;
    j->name = name;
    j->atoms = (struct atom **)allocate(sizeof(struct atom *) * 4);
    j->num_atoms = 4;
    j->atoms[0] = translateAtomID(p, atomID1);
    j->atoms[1] = translateAtomID(p, atomID2);
    j->atoms[2] = translateAtomID(p, atomID3);
    j->atoms[3] = translateAtomID(p, atomID4);
}

// Create an angle meter jig in this part, given the jig name, and the
// three atoms to measure.  The angle between the atoms will be
// reported in the trace file.
void
makeAngleMeter(struct part *p, char *name, int atomID1, int atomID2, int atomID3)
{
    struct jig *j = newJig(p);
    
    j->type = AngleMeter;
    j->name = name;
    j->atoms = (struct atom **)allocate(sizeof(struct atom *) * 3);
    j->num_atoms = 3;
    j->atoms[0] = translateAtomID(p, atomID1);
    j->atoms[1] = translateAtomID(p, atomID2);
    j->atoms[2] = translateAtomID(p, atomID3);
}

// Create a radius jig in this part, given the jig name, and the two
// atoms to measure.  The disance between the atoms will be reported
// in the trace file.
void
makeRadiusMeter(struct part *p, char *name, int atomID1, int atomID2)
{
    struct jig *j = newJig(p);
    
    j->type = RadiusMeter;
    j->name = name;
    j->atoms = (struct atom **)allocate(sizeof(struct atom *) * 2);
    j->num_atoms = 2;
    j->atoms[0] = translateAtomID(p, atomID1);
    j->atoms[1] = translateAtomID(p, atomID2);
}

// Create a thermostat jig in this part, given the name of the jig,
// the set point temperature, and the range of atoms to include.
// Kinetic energy will be added or removed from the given range of
// atoms to maintain the given temperature.
void
makeThermostat(struct part *p, char *name, double temperature, int firstAtomID, int lastAtomID)
{
    struct jig *j = newJig(p);
    
    j->type = Thermostat;
    j->name = name;
    j->j.thermostat.temperature = temperature;
    jigAtomRange(p, j, firstAtomID, lastAtomID);
}

// Empirically it looks like you don't want to go with a smaller
// flywheel than this.
#define MIN_MOMENT  5.0e-20

// Create a rotary motor jig in this part, given the name of the jig,
// parameters controlling the motor, and the list of atoms to include.
// The motor rotates around the center point, with the plane of
// rotation perpendicular to the direction of the axis vector.
//
// (XXX need good description of behavior of stall and speed)
// stall torque is in nN-nm
// speed is in GHz
struct jig *
makeRotaryMotor(struct part *p, char *name,
                double stall, double speed,
                struct xyz *center, struct xyz *axis,
                int atomListLength, int *atomList)
{
    int i, k;
    double mass;
    struct jig *j = newJig(p);
    
    j->type = RotaryMotor;
    j->name = name;
    j->degreesOfFreedom = 1; // the angle the motor has rotated by in radians

    // Example uses 1 nN-nm -> 1e6 pN-pm
    // Example uses 2 GHz -> 12.5664e9 radians/second

    // convert nN-nm to pN-pm (multiply by 1e6)
    // torque's sign is meaningless, force it positive
    j->j.rmotor.stall = fabs(stall) * (1e-9/Dx) * (1e-9/Dx);

    // this will do until we get a separate number in the mmp record
    // minimizeTorque is in aN m (1e-18 N m, or 1e-9 N 1e-9 m, or nN nm)
    j->j.rmotor.minimizeTorque = fabs(stall);
    
    // convert from gigahertz to radians per second
    j->j.rmotor.speed = speed * 2.0e9 * Pi;
    // critical damping gets us up to speed as quickly as possible
    // http://hyperphysics.phy-astr.gsu.edu/hbase/oscda2.html
    j->j.rmotor.dampingCoefficient = 0.7071;
    j->j.rmotor.damping_enabled = 1;
    j->j.rmotor.center = *center;
    j->j.rmotor.axis = uvec(*axis);
    // axis now has a length of one
    jigAtomList(p, j, atomListLength, atomList);
    
    j->j.rmotor.u = (struct xyz *)allocate(sizeof(struct xyz) * atomListLength);
    j->j.rmotor.v = (struct xyz *)allocate(sizeof(struct xyz) * atomListLength);
    j->j.rmotor.w = (struct xyz *)allocate(sizeof(struct xyz) * atomListLength);
    j->j.rmotor.rPrevious = (struct xyz *)allocate(sizeof(struct xyz) * atomListLength);
    j->j.rmotor.momentOfInertia = 0.0;
    for (i = 0; i < j->num_atoms; i++) {
	struct xyz r, v;
	double lenv;
	k = j->atoms[i]->index;
	/* for each atom connected to the motor */
	mass = j->atoms[i]->mass * 1e-27;
	
	/* u, v, and w can be used to compute the new anchor position from
	 * theta. The new position is u + v cos(theta) + w sin(theta). u is
	 * parallel to the motor axis, v and w are perpendicular to the axis
	 * and perpendicular to each other and the same length.
	 */
	r = vdif(p->positions[k], j->j.rmotor.center);
	vmul2c(j->j.rmotor.u[i], j->j.rmotor.axis, vdot(r, j->j.rmotor.axis));
	v = r;
	vsub(v, j->j.rmotor.u[i]);
	lenv = vlen(v);
	j->j.rmotor.v[i] = v;
	j->j.rmotor.w[i] = vx(j->j.rmotor.axis, v);
	j->j.rmotor.momentOfInertia += mass * lenv * lenv;
	vsetc(j->j.rmotor.rPrevious[i], 0.0);
    }
    
    // Add a flywheel with many times the moment of inertia of the atoms
    j->j.rmotor.momentOfInertia *= 11.0;
    if (j->j.rmotor.momentOfInertia < MIN_MOMENT)
	j->j.rmotor.momentOfInertia = MIN_MOMENT;
    j->j.rmotor.theta = 0.0;
    j->j.rmotor.omega = 0.0;
    return j;
}

// set initial speed of rotary motor
// initialSpeed in GHz
// rmotor.omega in radians per second
void
setInitialSpeed(struct jig *j, double initialSpeed)
{
    j->j.rmotor.omega = initialSpeed * 2.0e9 * Pi;
    // maybe also set minimizeTorque
}

void
setDampingCoefficient(struct jig *j, double dampingCoefficient)
{
    j->j.rmotor.dampingCoefficient = dampingCoefficient;
}

void
setDampingEnabled(struct jig *j, int dampingEnabled)
{
    j->j.rmotor.damping_enabled = dampingEnabled;
}

// Create a linear motor jig in this part, given the name of the jig,
// parameters controlling the motor, and the list of atoms to include.
// Atoms in the jig are constrained to move in the direction given by
// the axis vector.  A constant force can be applied, or they can be
// connected to a spring of the given stiffness.
//
// Jig output is the change in the averge of the positions of all of
// the atoms in the motor from the input positions.
//
// When stiffness is zero, force is uniformly divided among the atoms.
//
// When stiffness is non-zero, it represents a spring connecting the
// center of the atoms to a point along the motor axis from that
// point.  The force parameter is used to determine where the spring
// is attached.  The spring attachment point is such that the initial
// force on the motor is the force parameter.  The force from the
// spring is always evenly divided among the atoms.
void
makeLinearMotor(struct part *p, char *name,
                double force, double stiffness,
                struct xyz *center, struct xyz *axis,
                int atomListLength, int *atomList)
{
    int i;
    double x;
    struct xyz centerOfAtoms;
    struct jig *j = newJig(p);
    
    j->type = LinearMotor;
    j->name = name;
    // linear motor is not a distinct object which can move on its
    // own, it's just a function of the average location of its atoms,
    // so it has no independant degrees of freedom.
    //j->degreesOfFreedom = 1; // distance motor has moved in pm.
    
    j->j.lmotor.force = force; // in pN
    j->j.lmotor.stiffness = stiffness; // in N/m
    j->j.lmotor.axis = uvec(*axis);
    jigAtomList(p, j, atomListLength, atomList);
    
    centerOfAtoms = vcon(0.0);
    for (i=0; i<atomListLength; i++) {
	centerOfAtoms = vsum(centerOfAtoms, p->positions[j->atoms[i]->index]);
    }
    centerOfAtoms = vprodc(centerOfAtoms, 1.0 / atomListLength);
    
    // x is length of projection of centerOfAtoms onto axis (from
    // origin, not center)
    x = vdot(centerOfAtoms, j->j.lmotor.axis);
    j->j.lmotor.motorPosition = x;
    
    if (stiffness == 0.0) {
	j->j.lmotor.zeroPosition = x;
	j->j.lmotor.constantForce = vprodc(j->j.lmotor.axis, force / atomListLength);
    } else {
	j->j.lmotor.zeroPosition = x + force / stiffness ;
        vsetc(j->j.lmotor.constantForce, 0.0);
    }
}

void
printXYZ(FILE *f, struct xyz p)
{
    fprintf(f, "(%f, %f, %f)", p.x, p.y, p.z);
}

void
printQuaternion(FILE *f, struct quaternion q)
{
    fprintf(f, "(%f i, %f j, %f k, %f)", q.x, q.y, q.z, q.a);
}

void
printInertiaTensor(FILE *f, double *t)
{
    fprintf(f, "/ %14.7e %14.7e %14.7e \\\n", t[0], t[1], t[2]);
    fprintf(f, "| %14s %14.7e %14.7e |\n", "", t[3], t[4]);
    fprintf(f, "\\ %14s %14s %14.7e /\n", "", "", t[5]);
}


void
printAtomShort(FILE *f, struct atom *a)
{
    fprintf(f, "%s(%d)", a->type->symbol, a->atomID);
}

char
printableBondOrder(struct bond *b)
{
    switch (b->order) {
    case '1':
	return '-' ;
	break;
    case '2':
	return '=' ;
	break;
    case '3':
	return '+' ;
	break;
    case 'a':
	return '@' ;
	break;
    case 'g':
	return '#' ;
	break;
    case 'c':
	return '~' ;
	break;
    default:
	return b->order;
	break;
    }
}

char *
hybridizationString(enum hybridization h)
{
    switch (h) {
    case sp:
        return "sp";
    case sp2:
        return "sp2";
    case sp2_g:
        return "sp2_g";
    case sp3:
        return "sp3";
    case sp3d:
        return "sp3d";
    default:
        return "???";
    }
}

void
printAtom(FILE *f, struct part *p, struct atom *a)
{
    int i;
    struct bond *b;
    
    fprintf(f, " atom ");
    printAtomShort(f, a);
    fprintf(f, ".%s ", hybridizationString(a->hybridization));
    printXYZ(f, p->positions[a->index]);
    for (i=0; i<a->num_bonds; i++) {
	fprintf(f, " ");
	b = a->bonds[i];
	fprintf(f, "%c", printableBondOrder(b));
	CHECK_VALID_BOND(b);
	if (b->a1 == a) {
	    printAtomShort(f, b->a2);
	} else if (b->a2 == a) {
	    printAtomShort(f, b->a1);
	} else {
	    fprintf(f, "!!! improper bond on atom: ");
	    printAtomShort(f, b->a1);
	    printAtomShort(f, b->a2);
	}
    }
    fprintf(f, "\n");
}

void
printBond(FILE *f, struct part *p, struct bond *b)
{
    fprintf(f, " bond ");
    CHECK_VALID_BOND(b);
    printAtomShort(f, b->a1);
    fprintf(f, "%c", printableBondOrder(b));
    printAtomShort(f, b->a2);
    fprintf(f, "\n");
}

char *
printableJigType(struct jig *j)
{
    switch (j->type) {
    case Ground:        return "Ground";
    case Thermometer:   return "Thermometer";
    case DihedralMeter: return "DihedralMeter";
    case AngleMeter:    return "AngleMeter";
    case RadiusMeter:   return "RadiusMeter";
    case Thermostat:    return "Thermostat";
    case RotaryMotor:   return "RotaryMotor";
    case LinearMotor:   return "LinearMotor";
    default:            return "unknown";
    }
}

void
printJig(FILE *f, struct part *p, struct jig *j)
{
    int i;
    
    fprintf(f, " %s jig (%s)", printableJigType(j), j->name);
    for (i=0; i<j->num_atoms; i++) {
	fprintf(f, " ");
	printAtomShort(f, j->atoms[i]);
    }
    fprintf(f, "\n");
    switch (j->type) {
    case Thermostat:
	fprintf(f, "  temperature: %f\n", j->j.thermostat.temperature);
	break;
    case RotaryMotor:
	fprintf(f, "  stall torque: %13.10e pN-pm\n", j->j.rmotor.stall);
	fprintf(f, "  top speed: %13.10e radians per second\n", j->j.rmotor.speed);
	fprintf(f, "  current speed: %13.10e radians per second\n", j->j.rmotor.omega);
	fprintf(f, "  minimize torque: %13.10e pN-pm\n", j->j.rmotor.minimizeTorque * 1e6);
	fprintf(f, "  damping: %13.10e\n", j->j.rmotor.damping_enabled ? j->j.rmotor.dampingCoefficient : 0.0);
	fprintf(f, "  center: ");
	printXYZ(f, j->j.rmotor.center);
	fprintf(f, "\n");
	fprintf(f, "  axis: ");
	printXYZ(f, j->j.rmotor.axis);
	fprintf(f, "\n");
	break;
    case LinearMotor:
	fprintf(f, "  force: %f\n", j->j.lmotor.force);
	fprintf(f, "  stiffness: %f\n", j->j.lmotor.stiffness);
	fprintf(f, "  constantForce: ");
	printXYZ(f, j->j.lmotor.constantForce);
	fprintf(f, "\n");
	fprintf(f, "  axis: ");
	printXYZ(f, j->j.lmotor.axis);
	fprintf(f, "\n");
	break;
    default:
	break;
    }
}

static void
printJointType(FILE *f, enum jointType type)
{
    switch (type) {
    case BallSocket:
        fprintf(f, "BallSocket");
        break;
    case Hinge:
        fprintf(f, "Hinge");
        break;
    default:
        fprintf(f, "*Unknown*");
        break;
    }
}

void
printJoint(FILE *f, struct part *p, struct joint *j)
{
    fprintf(f, " ");
    printJointType(f, j->type);
    fprintf(f, " joint between (%s) and (%s)\n", p->rigidBodies[j->rigidBody1].name, p->rigidBodies[j->rigidBody2].name);
}

void
printRigidBody(FILE *f, struct part *p, struct rigidBody *rb)
{
    int i;
    
    fprintf(f, " rigidBody (%s)\n", rb->name);
    fprintf(f, "  position: ");
    printXYZ(f, rb->position);
    fprintf(f, "\n  orientation: ");
    printQuaternion(f, rb->orientation);
    fprintf(f, "\n  mass: %f\n  inertiaTensor:\n", rb->mass);
    printInertiaTensor(f, rb->inertiaTensor);
    if (rb->num_stations > 0) {
        fprintf(f, "  stations:\n");
        for (i=0; i<rb->num_stations; i++) {
            fprintf(f, "   (%s) ", rb->stationNames[i]);
            printXYZ(f, rb->stations[i]);
            fprintf(f, "\n");
        }
    }
    if (rb->num_axies > 0) {
        fprintf(f, "  axies:\n");
        for (i=0; i<rb->num_axies; i++) {
            fprintf(f, "   (%s) ", rb->axisNames[i]);
            printXYZ(f, rb->axies[i]);
            fprintf(f, "\n");
        }
    }
    if (rb->num_joints > 0) {
        fprintf(f, "  joints: ");
        for (i=0; i<rb->num_joints; i++) {
            printJoint(f, p, &rb->joints[i]);
        }
        fprintf(f, "\n");
    }
}

void
printVanDerWaals(FILE *f, struct part *p, struct vanDerWaals *v)
{
    double len;
    double potential;
    double gradient;
    struct xyz p1;
    struct xyz p2;
    
    if (v != NULL) {
	fprintf(f, " vanDerWaals ");
	CHECK_VALID_BOND(v);
	printAtomShort(f, v->a1);
	fprintf(f, " ");
	printAtomShort(f, v->a2);
	
	p1 = p->positions[v->a1->index];
	p2 = p->positions[v->a2->index];
	vsub(p1, p2);
	len = vlen(p1);
	
	
	potential = vanDerWaalsPotential(NULL, NULL, v->parameters, len);
	gradient = vanDerWaalsGradient(NULL, NULL, v->parameters, len);
	fprintf(f, " r: %f r0: %f, V: %f, dV: %f\n", len, v->parameters->rvdW, potential, gradient);
    }
}

void
printStretch(FILE *f, struct part *p, struct stretch *s)
{
    double len;
    double potential;
    double gradient;
    struct xyz p1;
    struct xyz p2;
    
    CHECK_VALID_BOND(s);
    fprintf(f, " stretch ");
    printAtomShort(f, s->a1);
    fprintf(f, ", ");
    printAtomShort(f, s->a2);
    fprintf(f, ":  %s ", s->stretchType->bondName);
    
    p1 = p->positions[s->a1->index];
    p2 = p->positions[s->a2->index];
    vsub(p1, p2);
    len = vlen(p1);
    
    potential = stretchPotential(NULL, NULL, s->stretchType, len);
    gradient = stretchGradient(NULL, NULL, s->stretchType, len);
    fprintf(f, "r: %f r0: %f, V: %f, dV: %f\n", len, s->stretchType->r0, potential, gradient);
}

void
printBend(FILE *f, struct part *p, struct bend *b)
{
    double invlen;
    double costheta;
    double theta;
    double dTheta;
    double potential;
    //double z;
    struct xyz p1;
    struct xyz pc;
    struct xyz p2;
    
    CHECK_VALID_BOND(b);
    fprintf(f, " bend ");
    printAtomShort(f, b->a1);
    fprintf(f, ", ");
    printAtomShort(f, b->ac);
    fprintf(f, ", ");
    printAtomShort(f, b->a2);
    fprintf(f, ":  %s ", b->bendType->bendName);
    
    p1 = p->positions[b->a1->index];
    pc = p->positions[b->ac->index];
    p2 = p->positions[b->a2->index];
    
    vsub(p1, pc);
    invlen = 1.0 / vlen(p1);
    vmulc(p1, invlen); // p1 is now unit vector from ac to a1
    
    vsub(p2, pc);
    invlen = 1.0 / vlen(p2);
    vmulc(p2, invlen); // p2 is now unit vector from ac to a2
    
    costheta = vdot(p1, p2);
    theta = acos(costheta);
    fprintf(f, "theta: %f ", theta * 180.0 / Pi);
    
#if 0
    z = vlen(vsum(p1, p2)); // z is length of cord between where bonds intersect unit sphere
    
#define ACOS_POLY_A -0.0820599
#define ACOS_POLY_B  0.142376
#define ACOS_POLY_C -0.137239
#define ACOS_POLY_D -0.969476
    
    // this is the equivalent of theta=arccos(z);
    theta = Pi + z * (ACOS_POLY_D +
		      z * (ACOS_POLY_C +
			   z * (ACOS_POLY_B +
				z *  ACOS_POLY_A   )));
    
    fprintf(f, "polytheta: %f ", theta * 180.0 / Pi);
#endif
    
    dTheta = (theta - b->bendType->theta0);
    potential = 1e-6 * 0.5 * dTheta * dTheta * b->bendType->kb;
    
    fprintf(f, "theta0: %f dTheta: %f, V: %f\n", b->bendType->theta0 * 180.0 / Pi, dTheta * 180.0 / Pi, potential);
}

void
printTorsion(FILE *f, struct part *p, struct torsion *t)
{
    NULLPTR(t);
    NULLPTR(t->a1);
    NULLPTR(t->aa);
    NULLPTR(t->ab);
    NULLPTR(t->a2);
    fprintf(f, " torsion ");
    printAtomShort(f, t->a1);
    fprintf(f, " - ");
    printAtomShort(f, t->aa);
    fprintf(f, " = ");
    printAtomShort(f, t->ab);
    fprintf(f, " - ");
    printAtomShort(f, t->a2);
    fprintf(f, "\n");
}

void
printCumuleneTorsion(FILE *f, struct part *p, struct cumuleneTorsion *t)
{
    NULLPTR(t);
    NULLPTR(t->a1);
    NULLPTR(t->aa);
    NULLPTR(t->ab);
    NULLPTR(t->ay);
    NULLPTR(t->az);
    NULLPTR(t->a2);
    fprintf(f, " cumuleneTorsion ");
    printAtomShort(f, t->a1);
    fprintf(f, " - ");
    printAtomShort(f, t->aa);
    fprintf(f, " = ");
    printAtomShort(f, t->ab);
    fprintf(f, " ... ");
    printAtomShort(f, t->ay);
    fprintf(f, " = ");
    printAtomShort(f, t->az);
    fprintf(f, " - ");
    printAtomShort(f, t->a2);
    fprintf(f, " chain length %d double bonds\n", t->numberOfDoubleBonds);
}

void
printOutOfPlane(FILE *f, struct part *p, struct outOfPlane *o)
{
    NULLPTR(o);
    NULLPTR(o->ac);
    NULLPTR(o->a1);
    NULLPTR(o->a2);
    NULLPTR(o->a3);
    fprintf(f, " outOfPlane ");
    printAtomShort(f, o->ac);
    fprintf(f, " - (");
    printAtomShort(f, o->a1);
    fprintf(f, ", ");
    printAtomShort(f, o->a2);
    fprintf(f, ", ");
    printAtomShort(f, o->a3);
    fprintf(f, ")\n");
}

void
printPart(FILE *f, struct part *p)
{
    int i;
    
    fprintf(f, "part loaded from file %s\n", p->filename);
    for (i=0; i<p->num_atoms; i++) {
	printAtom(f, p, p->atoms[i]);
    }
    for (i=0; i<p->num_bonds; i++) {
	printBond(f, p, p->bonds[i]);
    }
    for (i=0; i<p->num_jigs; i++) {
	printJig(f, p, p->jigs[i]);
    }
    for (i=0; i<p->num_rigidBodies; i++) {
	printRigidBody(f, p, &p->rigidBodies[i]);
    }
    for (i=0; i<p->num_vanDerWaals; i++) {
	printVanDerWaals(f, p, p->vanDerWaals[i]);
    }
    for (i=0; i<p->num_stretches; i++) {
	printStretch(f, p, &p->stretches[i]);
    }
    for (i=0; i<p->num_bends; i++) {
	printBend(f, p, &p->bends[i]);
    }
    for (i=0; i<p->num_torsions; i++) {
	printTorsion(f, p, &p->torsions[i]);
    }
    for (i=0; i<p->num_cumuleneTorsions; i++) {
	printCumuleneTorsion(f, p, &p->cumuleneTorsions[i]);
    }
    for (i=0; i<p->num_outOfPlanes; i++) {
	printOutOfPlane(f, p, &p->outOfPlanes[i]);
    }
}

/*
 * Local Variables:
 * c-basic-offset: 4
 * tab-width: 8
 * End:
 */
