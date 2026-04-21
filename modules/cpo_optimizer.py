"""
CPO Optimizer Module
====================
Analyzes Cost Per Order (CPO) and generates optimization recommendations.

Usage:
    from cpo_optimizer import CPOOptimizer
    
    optimizer = CPOOptimizer(target_cpo=1.52)
    analysis = optimizer.analyze_costs(cluster_df)
    recommendations = optimizer.generate_recommendations(cluster_df)
"""

import pandas as pd
import numpy as np
from datetime import datetime


class CPOOptimizer:
    """Analyzes CPO and generates cost-saving recommendations"""
    
    def __init__(self, target_cpo=None, excel_path=None):
        """
        Initialize CPO Optimizer
        
        Parameters:
        -----------
        target_cpo : float, optional
            Target CPO to optimize towards (default: median of data)
        excel_path : str, optional
            Path to Clusters_cost_saving.xlsx file
        """
        self.target_cpo = target_cpo
        self.excel_path = excel_path
        self.cpo_data = None
        self.sop_data = None
        
        if excel_path:
            self.load_excel_data(excel_path)
    
    def load_excel_data(self, excel_path):
        """Load CPO and SOP data from Excel file"""
        try:
            # Load working sheet with CPO data
            working_df = pd.read_excel(excel_path, sheet_name='Working sheet')
            
            # Create pincode to CPO lookup
            self.cpo_data = working_df.set_index('Pincode')['CPO'].to_dict()
            
            # Load SOP compliance data
            sop_compliant = pd.read_excel(excel_path, sheet_name='SOP compliant')
            non_sop = pd.read_excel(excel_path, sheet_name='Non SOP')
            
            self.sop_data = {
                'compliant': set(sop_compliant['Pincode'].unique()) if 'Pincode' in sop_compliant.columns else set(),
                'non_compliant': set(non_sop['Pincode'].unique()) if 'Pincode' in non_sop.columns else set()
            }
            
            print(f"Loaded CPO data for {len(self.cpo_data)} pincodes")
            print(f"Loaded SOP data: {len(self.sop_data['compliant'])} compliant, {len(self.sop_data['non_compliant'])} non-compliant")
            
        except Exception as e:
            print(f"Warning: Could not load Excel data: {e}")
            self.cpo_data = {}
            self.sop_data = {'compliant': set(), 'non_compliant': set()}
    
    def enrich_cluster_data(self, cluster_df):
        """
        Add CPO and SOP data to cluster dataframe
        
        Parameters:
        -----------
        cluster_df : DataFrame
            Cluster data with 'pincode' column
            
        Returns:
        --------
        DataFrame with added columns: cpo, cpo_category, sop_compliant, etc.
        """
        enriched_df = cluster_df.copy()
        
        # Add CPO data
        if self.cpo_data:
            enriched_df['cpo'] = enriched_df['pincode'].map(self.cpo_data)
        elif 'cpo' not in enriched_df.columns:
            enriched_df['cpo'] = np.nan
        
        # Categorize CPO
        enriched_df['cpo_category'] = enriched_df['cpo'].apply(self._categorize_cpo)
        
        # Add SOP compliance
        if self.sop_data:
            enriched_df['sop_compliant'] = enriched_df['pincode'].isin(self.sop_data['compliant'])
        elif 'sop_compliant' not in enriched_df.columns:
            enriched_df['sop_compliant'] = True  # Assume compliant if no data
        
        # Calculate target CPO if not set
        if self.target_cpo is None:
            self.target_cpo = enriched_df['cpo'].median()
        
        enriched_df['target_cpo'] = self.target_cpo
        
        # Calculate excess CPO
        enriched_df['excess_cpo'] = (enriched_df['cpo'] - self.target_cpo).clip(lower=0)
        
        # Estimate monthly orders (default 1000, can be customized)
        if 'avg_monthly_orders' not in enriched_df.columns:
            enriched_df['avg_monthly_orders'] = 1000
        
        # Calculate savings potential
        enriched_df['monthly_saving_potential'] = (
            enriched_df['excess_cpo'] * enriched_df['avg_monthly_orders']
        )
        enriched_df['annual_saving_potential'] = enriched_df['monthly_saving_potential'] * 12
        
        # Calculate optimization priority
        enriched_df['optimization_priority'] = enriched_df.apply(
            lambda row: self._calculate_priority(
                row.get('excess_cpo', 0),
                row.get('monthly_saving_potential', 0)
            ),
            axis=1
        )
        
        return enriched_df
    
    def analyze_costs(self, cluster_df):
        """
        Comprehensive cost analysis
        
        Returns:
        --------
        dict with analysis results
        """
        # Enrich data if needed
        if 'cpo' not in cluster_df.columns or cluster_df['cpo'].isna().all():
            cluster_df = self.enrich_cluster_data(cluster_df)
        
        # Calculate statistics
        cpo_series = cluster_df['cpo'].dropna()
        
        if len(cpo_series) == 0:
            return {
                'error': 'No CPO data available',
                'total_clusters': len(cluster_df)
            }
        
        if self.target_cpo is None:
            self.target_cpo = cpo_series.median()
        
        analysis = {
            'summary': {
                'total_clusters': len(cluster_df),
                'clusters_with_cpo': len(cpo_series),
                'avg_cpo': float(cpo_series.mean()),
                'median_cpo': float(cpo_series.median()),
                'min_cpo': float(cpo_series.min()),
                'max_cpo': float(cpo_series.max()),
                'std_cpo': float(cpo_series.std()),
                'target_cpo': float(self.target_cpo)
            },
            
            'distribution': {
                'low_0_1.5': len(cluster_df[cluster_df['cpo'] < 1.5]),
                'medium_1.5_2.0': len(cluster_df[(cluster_df['cpo'] >= 1.5) & (cluster_df['cpo'] < 2.0)]),
                'high_2.0_2.5': len(cluster_df[(cluster_df['cpo'] >= 2.0) & (cluster_df['cpo'] < 2.5)]),
                'very_high_2.5_3.0': len(cluster_df[(cluster_df['cpo'] >= 2.5) & (cluster_df['cpo'] < 3.0)]),
                'critical_3.0_plus': len(cluster_df[cluster_df['cpo'] >= 3.0])
            },
            
            'savings_potential': {
                'clusters_above_target': len(cluster_df[cluster_df['cpo'] > self.target_cpo]),
                'total_excess_cpo': float(cluster_df['excess_cpo'].sum()),
                'avg_excess_cpo': float(cluster_df[cluster_df['excess_cpo'] > 0]['excess_cpo'].mean()),
                'monthly_savings': float(cluster_df['monthly_saving_potential'].sum()),
                'annual_savings': float(cluster_df['annual_saving_potential'].sum())
            },
            
            'sop_compliance': {
                'total_compliant': len(cluster_df[cluster_df['sop_compliant'] == True]),
                'total_non_compliant': len(cluster_df[cluster_df['sop_compliant'] == False]),
                'compliance_rate': float(len(cluster_df[cluster_df['sop_compliant'] == True]) / len(cluster_df) * 100)
            }
        }
        
        return analysis
    
    def generate_recommendations(self, cluster_df, max_recommendations=20):
        """
        Generate prioritized cost optimization recommendations
        
        Parameters:
        -----------
        cluster_df : DataFrame
            Enriched cluster data
        max_recommendations : int
            Maximum number of recommendations to return
            
        Returns:
        --------
        DataFrame with recommendations
        """
        # Enrich data if needed
        if 'excess_cpo' not in cluster_df.columns:
            cluster_df = self.enrich_cluster_data(cluster_df)
        
        # Filter clusters above target with valid CPO
        high_cost = cluster_df[
            (cluster_df['cpo'] > self.target_cpo) & 
            (cluster_df['cpo'].notna())
        ].copy()
        
        if len(high_cost) == 0:
            return pd.DataFrame(columns=[
                'rank', 'cluster_code', 'hub_name', 'pincode',
                'current_cpo', 'target_cpo', 'excess_cpo',
                'monthly_saving', 'annual_saving', 'priority',
                'action', 'effort', 'risk'
            ])
        
        # Sort by savings potential
        high_cost = high_cost.sort_values('monthly_saving_potential', ascending=False)
        
        recommendations = []
        
        for idx, cluster in high_cost.head(max_recommendations).iterrows():
            rec = {
                'rank': len(recommendations) + 1,
                'cluster_code': cluster.get('cluster_code', 'N/A'),
                'hub_name': cluster.get('hub_name', 'N/A'),
                'pincode': cluster.get('pincode', 'N/A'),
                'current_cpo': float(cluster['cpo']),
                'target_cpo': float(self.target_cpo),
                'excess_cpo': float(cluster['excess_cpo']),
                'monthly_orders': int(cluster.get('avg_monthly_orders', 1000)),
                'monthly_saving': float(cluster['monthly_saving_potential']),
                'annual_saving': float(cluster['annual_saving_potential']),
                'priority': cluster['optimization_priority'],
                'action': self._suggest_action(cluster),
                'effort': self._estimate_effort(cluster),
                'risk': self._assess_risk(cluster),
                'sop_compliant': cluster.get('sop_compliant', True)
            }
            recommendations.append(rec)
        
        return pd.DataFrame(recommendations)
    
    def hub_benchmarking(self, cluster_df):
        """
        Benchmark hubs by cost efficiency
        
        Returns:
        --------
        DataFrame with hub-level statistics
        """
        # Enrich data if needed
        if 'cpo' not in cluster_df.columns:
            cluster_df = self.enrich_cluster_data(cluster_df)
        
        # Group by hub
        hub_stats = cluster_df.groupby('hub_name').agg({
            'cpo': ['mean', 'min', 'max', 'std', 'count'],
            'monthly_saving_potential': 'sum',
            'sop_compliant': 'mean',
            'cluster_code': 'count'
        }).round(2)
        
        hub_stats.columns = [
            'avg_cpo', 'min_cpo', 'max_cpo', 'cpo_variance', 'cpo_data_count',
            'total_savings_potential', 'sop_compliance_rate', 'total_clusters'
        ]
        
        # Calculate performance score
        hub_stats['performance_score'] = self._calculate_hub_score(hub_stats)
        
        # Add ranking
        hub_stats['rank'] = hub_stats['performance_score'].rank(ascending=False, method='dense').astype(int)
        
        return hub_stats.sort_values('performance_score', ascending=False)
    
    # ========== PRIVATE HELPER METHODS ==========
    
    @staticmethod
    def _categorize_cpo(cpo):
        """Categorize CPO into buckets"""
        if pd.isna(cpo):
            return "No Data"
        elif cpo < 1.5:
            return "Low (₹0-1.5)"
        elif cpo < 2.0:
            return "Medium (₹1.5-2.0)"
        elif cpo < 2.5:
            return "High (₹2.0-2.5)"
        elif cpo < 3.0:
            return "Very High (₹2.5-3.0)"
        else:
            return "Critical (₹3.0+)"
    
    @staticmethod
    def _calculate_priority(excess_cpo, monthly_saving):
        """Calculate optimization priority"""
        if excess_cpo > 1.5 and monthly_saving > 2000:
            return 'Critical'
        elif excess_cpo > 1.0 or monthly_saving > 1500:
            return 'High'
        elif excess_cpo > 0.5 or monthly_saving > 1000:
            return 'Medium'
        else:
            return 'Low'
    
    @staticmethod
    def _suggest_action(cluster):
        """Suggest specific action for cost reduction"""
        excess = cluster.get('excess_cpo', 0)
        
        if excess > 2.0:
            return "Urgent: Consider cluster merger or rate renegotiation"
        elif excess > 1.5:
            return "High: Review delivery routes and optimize logistics"
        elif excess > 1.0:
            return "Medium: Analyze cost drivers and implement efficiency measures"
        elif excess > 0.5:
            return "Low: Minor route optimization and monitoring"
        else:
            return "Maintain: Continue current operations"
    
    @staticmethod
    def _estimate_effort(cluster):
        """Estimate implementation effort"""
        excess = cluster.get('excess_cpo', 0)
        
        if excess > 2.0:
            return "High (3-4 weeks)"
        elif excess > 1.0:
            return "Medium (1-2 weeks)"
        else:
            return "Low (< 1 week)"
    
    @staticmethod
    def _assess_risk(cluster):
        """Assess risk of optimization"""
        if not cluster.get('sop_compliant', True):
            return "High - Non-SOP compliant, address compliance first"
        elif cluster.get('surge_amount', 0) > 5:
            return "Medium - High surge area, customer impact possible"
        else:
            return "Low - Safe to optimize"
    
    def _calculate_hub_score(self, hub_stats):
        """Calculate composite performance score (0-100)"""
        
        # CPO Score (40% weight) - Lower is better
        max_cpo = hub_stats['avg_cpo'].max()
        min_cpo = hub_stats['avg_cpo'].min()
        if max_cpo > min_cpo:
            cpo_score = ((max_cpo - hub_stats['avg_cpo']) / (max_cpo - min_cpo)) * 40
        else:
            cpo_score = 40
        
        # SOP Compliance Score (30% weight) - Higher is better
        compliance_score = hub_stats['sop_compliance_rate'] * 30
        
        # Consistency Score (20% weight) - Lower variance is better
        max_variance = hub_stats['cpo_variance'].max()
        if max_variance > 0:
            consistency_score = ((max_variance - hub_stats['cpo_variance']) / max_variance) * 20
        else:
            consistency_score = 20
        
        # Efficiency Score (10% weight) - Based on cluster management
        efficiency_score = 10
        
        total_score = cpo_score + compliance_score + consistency_score + efficiency_score
        
        return total_score.clip(0, 100)
    
    def export_recommendations(self, recommendations_df, filename=None):
        """Export recommendations to CSV"""
        if filename is None:
            filename = f"cost_optimization_recommendations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        recommendations_df.to_csv(filename, index=False)
        print(f"Recommendations exported to {filename}")
        return filename


# ========== UTILITY FUNCTIONS ==========

def format_currency(amount):
    """Format amount as Indian currency"""
    if amount >= 10000000:  # 1 crore
        return f"₹{amount/10000000:.2f}Cr"
    elif amount >= 100000:  # 1 lakh
        return f"₹{amount/100000:.2f}L"
    elif amount >= 1000:
        return f"₹{amount/1000:.1f}K"
    else:
        return f"₹{amount:.0f}"


def get_cpo_color(cpo):
    """Get color for CPO value"""
    if pd.isna(cpo):
        return '#9CA3AF'  # Gray
    elif cpo < 1.5:
        return '#10B981'  # Green - Low
    elif cpo < 2.0:
        return '#3B82F6'  # Blue - Medium
    elif cpo < 2.5:
        return '#F59E0B'  # Orange - High
    elif cpo < 3.0:
        return '#EF4444'  # Red - Very High
    else:
        return '#7F1D1D'  # Dark Red - Critical
